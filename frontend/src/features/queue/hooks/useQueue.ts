"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useActiveWorkspaceId, workspaceScopedQueryKey } from "@/lib/workspace";
import type { ApiError } from "@/services/api-client";
import {
  createQueueItem,
  deleteQueueItem,
  getQueue,
  getQueueItem,
  getQueuePublishAttempts,
  publishQueueItem,
  updateQueueItem,
} from "../api/queue.api";
import { createQueuePollIntervalSelector } from "../lib/queue-polling";
import type {
  QueueItem,
  QueuePublishFailure,
  QueueStatus,
  QueueTableDensity,
  QueueUpdate,
  QueueWorkspaceSort,
} from "../types/api";
import { useQueueRealtimePollingEnabled } from "./QueueRealtimePollingContext";

export const queueKey = (workspaceId: string) =>
  workspaceScopedQueryKey("queue", workspaceId);

export const queueAttemptsKey = (workspaceId: string, id: string) =>
  [...queueKey(workspaceId), "attempts", id] as const;

const ENRICHMENT_CONCURRENCY = 5;

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (
    error &&
    typeof error === "object" &&
    "message" in error &&
    typeof (error as ApiError).message === "string" &&
    (error as ApiError).message.length > 0
  ) {
    return (error as ApiError).message;
  }
  return fallback;
}

function isConflictError(error: unknown): boolean {
  return Boolean(
    error &&
      typeof error === "object" &&
      "status" in error &&
      (error as ApiError).status === 409,
  );
}

async function mapWithConcurrency<T, R>(
  items: readonly T[],
  concurrency: number,
  mapper: (item: T) => Promise<R>,
): Promise<R[]> {
  if (items.length === 0) return [];
  const results = new Array<R>(items.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < items.length) {
      const current = nextIndex;
      nextIndex += 1;
      results[current] = await mapper(items[current]);
    }
  }

  const workers = Array.from(
    { length: Math.min(concurrency, items.length) },
    () => worker(),
  );
  await Promise.all(workers);
  return results;
}

export function useQueue(status?: QueueStatus, limit = 20, skip = 0) {
  const workspaceId = useActiveWorkspaceId();
  const pollingEnabled = useQueueRealtimePollingEnabled();
  const refetchInterval = useMemo(
    () => (pollingEnabled ? createQueuePollIntervalSelector() : false),
    [pollingEnabled],
  );

  return useQuery({
    queryKey: workspaceId
      ? [...queueKey(workspaceId), status, limit, skip]
      : (["queue", "none", status, limit, skip] as const),
    queryFn: () => getQueue(status, limit, skip),
    enabled: Boolean(workspaceId),
    refetchInterval,
  });
}

/**
 * GET /queues does not populate attempt summary fields. Enrich non-published
 * items via GET /queues/{id} with limited concurrency after list load/invalidate.
 */
export function useQueueAttemptSummaryEnrichment(items: QueueItem[]) {
  const [summariesById, setSummariesById] = useState<
    Record<
      string,
      Pick<QueueItem, "last_attempt" | "failure_reason" | "retry_count">
    >
  >({});
  const [enriching, setEnriching] = useState(false);
  const generationRef = useRef(0);

  const listFingerprint = useMemo(
    () => items.map((item) => `${item.id}:${item.updated_at}`).join("|"),
    [items],
  );

  useEffect(() => {
    const generation = generationRef.current + 1;
    generationRef.current = generation;
    setSummariesById({});

    const targets = items.filter((item) => item.status !== "published");
    if (targets.length === 0) {
      setEnriching(false);
      return;
    }

    let cancelled = false;
    setEnriching(true);

    void (async () => {
      await mapWithConcurrency(targets, ENRICHMENT_CONCURRENCY, async (item) => {
        try {
          const detail = await getQueueItem(item.id);
          if (cancelled || generationRef.current !== generation) return;
          setSummariesById((previous) => ({
            ...previous,
            [item.id]: {
              last_attempt: detail.last_attempt ?? null,
              failure_reason: detail.failure_reason ?? null,
              retry_count: detail.retry_count ?? 0,
            },
          }));
        } catch {
          // Leave list defaults; client fallback / drawer fetch still apply.
        }
      });
      if (!cancelled && generationRef.current === generation) {
        setEnriching(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // Fingerprint captures id+updated_at churn after invalidate/refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- items via fingerprint
  }, [listFingerprint]);

  const enrichedItems = useMemo(
    () =>
      items.map((item) => {
        const summary = summariesById[item.id];
        return summary ? { ...item, ...summary } : item;
      }),
    [items, summariesById],
  );

  return { enrichedItems, enriching };
}

export function useQueuePublishAttempts(queueId: string | null, enabled: boolean) {
  const workspaceId = useActiveWorkspaceId();
  const pollingEnabled = useQueueRealtimePollingEnabled();
  const refetchInterval = useMemo(
    () => (pollingEnabled ? createQueuePollIntervalSelector() : false),
    [pollingEnabled],
  );

  return useQuery({
    queryKey:
      workspaceId && queueId
        ? queueAttemptsKey(workspaceId, queueId)
        : (["queue", workspaceId ?? "none", "attempts", queueId ?? "idle"] as const),
    queryFn: () => getQueuePublishAttempts(queueId!),
    enabled: enabled && Boolean(queueId) && Boolean(workspaceId),
    refetchInterval: enabled ? refetchInterval : false,
  });
}

export function useCreateQueueItem() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: createQueueItem,
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: queueKey(workspaceId) });
    },
  });
}

export function usePublishQueueItem() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: publishQueueItem,
    onSuccess: (_data, id) => {
      if (!workspaceId) return;
      void client.invalidateQueries({ queryKey: queueKey(workspaceId) });
      void client.invalidateQueries({ queryKey: queueAttemptsKey(workspaceId, id) });
    },
  });
}

export function useUpdateQueueItem() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: QueueUpdate }) =>
      updateQueueItem(id, input),
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: queueKey(workspaceId) });
    },
  });
}

export function useDeleteQueueItem() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: deleteQueueItem,
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: queueKey(workspaceId) });
    },
  });
}

export type PublishBatchResult = {
  published: number;
  failed: number;
  conflicts: number;
  /** Server detail for the first 409 (if any). */
  conflictMessage: string | null;
  /** Server detail for the first non-409 failure (if any). */
  failureMessage: string | null;
};

/**
 * In-flight `publishingIds` stay client-ephemeral.
 * `failures` is a short-lived fallback until attempt-summary enrichment arrives.
 * 409 conflicts toast with server detail and do not invent a failure row.
 */
export function useQueuePublishingOperations() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  const [publishingIds, setPublishingIds] = useState<string[]>([]);
  const [failures, setFailures] = useState<Record<string, QueuePublishFailure>>({});

  const publishItems = useCallback(
    async (ids: string[]): Promise<PublishBatchResult> => {
      const uniqueIds = Array.from(new Set(ids));
      setPublishingIds((previous) => Array.from(new Set([...previous, ...uniqueIds])));
      let published = 0;
      let failed = 0;
      let conflicts = 0;
      let conflictMessage: string | null = null;
      let failureMessage: string | null = null;

      for (const id of uniqueIds) {
        try {
          await publishQueueItem(id);
          published += 1;
          setFailures((previous) => {
            if (!(id in previous)) return previous;
            const next = { ...previous };
            delete next[id];
            return next;
          });
          if (workspaceId) {
            void client.invalidateQueries({
              queryKey: queueAttemptsKey(workspaceId, id),
            });
          }
        } catch (error) {
          const message = getApiErrorMessage(error, "تعذر النشر.");
          if (isConflictError(error)) {
            conflicts += 1;
            if (!conflictMessage) conflictMessage = message;
            // Idempotency suppression creates no attempt row — do not invent one.
          } else {
            failed += 1;
            if (!failureMessage) failureMessage = message;
            setFailures((previous) => ({
              ...previous,
              [id]: {
                message,
                occurredAt: new Date().toISOString(),
              },
            }));
          }
        } finally {
          setPublishingIds((previous) => previous.filter((value) => value !== id));
        }
      }

      if (workspaceId) {
        await client.invalidateQueries({ queryKey: queueKey(workspaceId) });
      }
      return { published, failed, conflicts, conflictMessage, failureMessage };
    },
    [client, workspaceId],
  );

  const clearFailure = useCallback((id: string) => {
    setFailures((previous) => {
      if (!(id in previous)) return previous;
      const next = { ...previous };
      delete next[id];
      return next;
    });
  }, []);

  /** Drop client fallback once backend summary is present for an item. */
  const syncFailuresFromBackend = useCallback((items: QueueItem[]) => {
    setFailures((previous) => {
      let changed = false;
      const next = { ...previous };
      for (const item of items) {
        if (!(item.id in next)) continue;
        if (item.last_attempt != null || item.failure_reason != null) {
          delete next[item.id];
          changed = true;
        }
      }
      return changed ? next : previous;
    });
  }, []);

  return {
    publishingIds,
    publishingIdSet: new Set(publishingIds),
    failures,
    publishItems,
    clearFailure,
    syncFailuresFromBackend,
  };
}

export function useQueueWorkspaceState(items: QueueItem[]) {
  const [selectedQueueItemIds, setSelectedQueueItemIds] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<QueueStatus | "">("");
  const [channelFilter, setChannelFilter] = useState("");
  const [sort, setSort] = useState<QueueWorkspaceSort>("newest");
  const [density, setDensity] = useState<QueueTableDensity>("comfortable");
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(0);

  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    const filtered = items.filter((item) => {
      const matchesSearch =
        !query ||
        [item.title, item.content, item.product_id]
          .filter(Boolean)
          .some((value) => String(value).toLocaleLowerCase().includes(query));
      const matchesStatus = !statusFilter || item.status === statusFilter;
      const matchesChannel =
        !channelFilter ||
        (channelFilter === "missing" ? !item.channel_id : item.channel_id === channelFilter);
      return matchesSearch && matchesStatus && matchesChannel;
    });

    return [...filtered].sort((left, right) => {
      switch (sort) {
        case "oldest":
          return Date.parse(left.created_at) - Date.parse(right.created_at);
        case "schedule_asc":
          return (
            Date.parse(left.scheduled_at ?? "9999-12-31") -
            Date.parse(right.scheduled_at ?? "9999-12-31")
          );
        case "schedule_desc":
          return (
            Date.parse(right.scheduled_at ?? "1970-01-01") -
            Date.parse(left.scheduled_at ?? "1970-01-01")
          );
        case "status":
          return left.status.localeCompare(right.status);
        case "newest":
        default:
          return Date.parse(right.created_at) - Date.parse(left.created_at);
      }
    });
  }, [items, search, statusFilter, channelFilter, sort]);

  const pagedItems = useMemo(
    () => filteredItems.slice(page * pageSize, (page + 1) * pageSize),
    [filteredItems, page, pageSize],
  );

  useEffect(() => {
    const validIds = new Set(items.map((item) => item.id));
    setSelectedQueueItemIds((previous) =>
      previous.filter((id) => validIds.has(id)),
    );
  }, [items]);

  useEffect(() => {
    setPage(0);
  }, [search, statusFilter, channelFilter, sort, pageSize]);

  const toggle = useCallback((id: string) => {
    setSelectedQueueItemIds((previous) =>
      previous.includes(id)
        ? previous.filter((value) => value !== id)
        : [...previous, id],
    );
  }, []);

  const toggleAll = useCallback(() => {
    const pageIds = pagedItems.map((item) => item.id);
    const allSelected =
      pageIds.length > 0 && pageIds.every((id) => selectedQueueItemIds.includes(id));
    setSelectedQueueItemIds((previous) =>
      allSelected
        ? previous.filter((id) => !pageIds.includes(id))
        : Array.from(new Set([...previous, ...pageIds])),
    );
  }, [pagedItems, selectedQueueItemIds]);

  return {
    selectedQueueItemIds,
    selectedItems: items.filter((item) => selectedQueueItemIds.includes(item.id)),
    filteredItems,
    pagedItems,
    allPageSelected:
      pagedItems.length > 0 &&
      pagedItems.every((item) => selectedQueueItemIds.includes(item.id)),
    search,
    statusFilter,
    channelFilter,
    sort,
    density,
    pageSize,
    page,
    setSearch,
    setStatusFilter,
    setChannelFilter,
    setSort,
    setDensity,
    setPageSize,
    setPage,
    toggle,
    toggleAll,
    clearSelection: () => setSelectedQueueItemIds([]),
  };
}

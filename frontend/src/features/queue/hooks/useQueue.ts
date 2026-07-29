"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createQueueItem,
  deleteQueueItem,
  getQueue,
  publishQueueItem,
  updateQueueItem,
} from "../api/queue.api";
import type {
  QueueItem,
  QueuePublishFailure,
  QueueStatus,
  QueueTableDensity,
  QueueUpdate,
  QueueWorkspaceSort,
} from "../types/api";

const queueKey = ["queue"] as const;

export function useQueue(status?: QueueStatus, limit = 20, skip = 0) {
  return useQuery({
    queryKey: [...queueKey, status, limit, skip],
    queryFn: () => getQueue(status, limit, skip),
  });
}

export function useCreateQueueItem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createQueueItem,
    onSuccess: () => client.invalidateQueries({ queryKey: queueKey }),
  });
}

export function usePublishQueueItem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: publishQueueItem,
    onSuccess: () => client.invalidateQueries({ queryKey: queueKey }),
  });
}

export function useUpdateQueueItem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: QueueUpdate }) =>
      updateQueueItem(id, input),
    onSuccess: () => client.invalidateQueries({ queryKey: queueKey }),
  });
}

export function useDeleteQueueItem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteQueueItem,
    onSuccess: () => client.invalidateQueries({ queryKey: queueKey }),
  });
}

export function useQueuePublishingOperations() {
  const client = useQueryClient();
  const [publishingIds, setPublishingIds] = useState<string[]>([]);
  const [failures, setFailures] = useState<Record<string, QueuePublishFailure>>({});

  const publishItems = useCallback(
    async (ids: string[]) => {
      const uniqueIds = Array.from(new Set(ids));
      setPublishingIds((previous) => Array.from(new Set([...previous, ...uniqueIds])));
      let published = 0;
      let failed = 0;

      for (const id of uniqueIds) {
        try {
          await publishQueueItem(id);
          published += 1;
          setFailures((previous) => {
            const next = { ...previous };
            delete next[id];
            return next;
          });
        } catch (error) {
          failed += 1;
          setFailures((previous) => ({
            ...previous,
            [id]: {
              message: error instanceof Error ? error.message : "Publishing failed",
              occurredAt: new Date().toISOString(),
            },
          }));
        } finally {
          setPublishingIds((previous) => previous.filter((value) => value !== id));
        }
      }

      await client.invalidateQueries({ queryKey: queueKey });
      return { published, failed };
    },
    [client],
  );

  const clearFailure = useCallback((id: string) => {
    setFailures((previous) => {
      const next = { ...previous };
      delete next[id];
      return next;
    });
  }, []);

  return {
    publishingIds,
    publishingIdSet: new Set(publishingIds),
    failures,
    publishItems,
    clearFailure,
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

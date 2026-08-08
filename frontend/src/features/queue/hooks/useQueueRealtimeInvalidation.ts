"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  QUEUE_EVENT_INVALIDATION_DEBOUNCE_MS,
  createDebouncedQueueEventInvalidator,
} from "../lib/queue-event-invalidation";
import { queueKey } from "./useQueue";
import {
  useQueueEventStream,
  type QueueEventStreamStatus,
} from "./useQueueEventStream";

export type UseQueueRealtimeInvalidationOptions = {
  enabled?: boolean;
  /** Override debounce window (tests may use 0). */
  debounceMs?: number;
};

export type UseQueueRealtimeInvalidationResult = {
  status: QueueEventStreamStatus;
  /**
   * When true, Queue TanStack Query hooks should enable refetchInterval
   * (SSE fallback). False while SSE is connected or during the first connect.
   */
  pollingEnabled: boolean;
};

/**
 * Queue workspace live-sync: one SSE subscription → debounced query invalidation.
 * On reconnect, refreshes authoritative queue queries (events are not replayed).
 * When SSE is unavailable after a live session (or explicit disconnect), enables
 * TanStack Query polling fallback (5s → 30s) until SSE is healthy again.
 */
export function useQueueRealtimeInvalidation(
  options: UseQueueRealtimeInvalidationOptions = {},
): UseQueueRealtimeInvalidationResult {
  const { enabled = true, debounceMs = QUEUE_EVENT_INVALIDATION_DEBOUNCE_MS } =
    options;
  const queryClient = useQueryClient();
  /**
   * Reconnect recovery must ignore a stale `connected` status that can linger
   * across StrictMode remounts (stream cleanup no longer setStates after abort).
   * Only a connecting → connected transition after the first established open
   * triggers invalidateQueries(["queue"]).
   */
  const sawConnectingRef = useRef(false);
  const establishedConnectionRef = useRef(false);
  const [pollingEnabled, setPollingEnabled] = useState(false);

  const invalidator = useMemo(
    () => createDebouncedQueueEventInvalidator(queryClient, debounceMs),
    [queryClient, debounceMs],
  );

  useEffect(() => () => invalidator.dispose(), [invalidator]);

  useEffect(() => {
    return () => {
      sawConnectingRef.current = false;
      establishedConnectionRef.current = false;
    };
  }, []);

  const { status } = useQueueEventStream({
    enabled,
    onEvent: (event) => {
      invalidator.handle(event);
    },
  });

  useEffect(() => {
    if (status === "connecting") {
      sawConnectingRef.current = true;
      return;
    }

    if (status !== "connected") return;

    // Stale connected from a previous mount — wait for a fresh connecting cycle.
    if (!sawConnectingRef.current) return;

    if (!establishedConnectionRef.current) {
      establishedConnectionRef.current = true;
      return;
    }

    // Reconnect recovery: refill any gap while disconnected (no event replay).
    void queryClient.invalidateQueries({ queryKey: queueKey });
  }, [status, queryClient]);

  useEffect(() => {
    if (!enabled) {
      sawConnectingRef.current = false;
      establishedConnectionRef.current = false;
      setPollingEnabled(false);
      return;
    }

    if (status === "connected" || status === "error") {
      setPollingEnabled(false);
      return;
    }

    if (status === "disconnected") {
      setPollingEnabled(true);
      return;
    }

    // `connecting` after a previously established live session = reconnecting.
    // Initial connect (never established) must not start fallback polling.
    setPollingEnabled(establishedConnectionRef.current);
  }, [status, enabled]);

  return { status, pollingEnabled };
}

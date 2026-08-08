"use client";

import { useEffect, useRef, useState } from "react";
import { session } from "@/services/session";
import {
  createQueueEventStream,
  type QueueSseError,
} from "../lib/sse-client";
import type { QueueEventEnvelope } from "../types/events";

/**
 * Connection lifecycle for the queue SSE foundation (Task F1).
 * Domain reactions (e.g. TanStack Query invalidation) belong in F2+ consumers
 * via {@link UseQueueEventStreamOptions.onEvent}.
 */
export type QueueEventStreamStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export type UseQueueEventStreamOptions = {
  /** When false, no connection is opened. Default true. */
  enabled?: boolean;
  /**
   * Optional event observer for domain reactions (invalidation, etc.).
   * Transport only delivers events — consumers decide what to do.
   */
  onEvent?: (event: QueueEventEnvelope) => void;
  onError?: (error: QueueSseError) => void;
};

export type UseQueueEventStreamResult = {
  status: QueueEventStreamStatus;
};

/**
 * React foundation for the authenticated queue SSE stream.
 * Connects on mount (when enabled + token present) and aborts on unmount.
 */
export function useQueueEventStream(
  options: UseQueueEventStreamOptions = {},
): UseQueueEventStreamResult {
  const { enabled = true } = options;
  const onEventRef = useRef(options.onEvent);
  const onErrorRef = useRef(options.onError);
  onEventRef.current = options.onEvent;
  onErrorRef.current = options.onError;

  const [status, setStatus] = useState<QueueEventStreamStatus>(() =>
    enabled ? "connecting" : "disconnected",
  );

  useEffect(() => {
    if (!enabled) {
      setStatus("disconnected");
      return;
    }

    const token = session.getAccessToken();
    if (!token) {
      setStatus("error");
      return;
    }

    const controller = new AbortController();
    let active = true;
    setStatus("connecting");

    void createQueueEventStream({
      token,
      signal: controller.signal,
      onOpen: () => {
        if (!active || controller.signal.aborted) return;
        setStatus("connected");
      },
      onMessage: (event) => {
        // Drop late frames after unmount/abort so they cannot invalidate queries.
        if (!active || controller.signal.aborted) return;
        onEventRef.current?.(event);
      },
      onReconnect: () => {
        if (!active || controller.signal.aborted) return;
        setStatus("connecting");
      },
      onError: (error) => {
        if (!active || controller.signal.aborted || error.kind === "abort") {
          return;
        }
        onErrorRef.current?.(error);
        if (error.fatal) {
          setStatus("error");
          return;
        }
        // Surface loss of the live stream before the reconnect sleep/backoff.
        // Polling fallback keys off `disconnected` / post-establish `connecting`.
        setStatus("disconnected");
      },
    }).finally(() => {
      // Avoid setState after unmount (cleanup sets active=false then aborts).
      if (!active) return;
      if (controller.signal.aborted) {
        setStatus("disconnected");
      }
    });

    return () => {
      active = false;
      controller.abort();
    };
  }, [enabled]);

  return { status };
}

"use client";

import { createContext, useContext } from "react";
import type { QueueEventStreamStatus } from "./useQueueEventStream";

/**
 * When true, queue and dashboard queries enable TanStack Query refetchInterval
 * as the SSE fallback. Provided by the operational realtime provider.
 */
export const QueueRealtimePollingContext = createContext(false);

export const QueueRealtimeStatusContext =
  createContext<QueueEventStreamStatus>("disconnected");

export function useQueueRealtimePollingEnabled(): boolean {
  return useContext(QueueRealtimePollingContext);
}

export function useQueueRealtimeStatus(): QueueEventStreamStatus {
  return useContext(QueueRealtimeStatusContext);
}

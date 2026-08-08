"use client";

import { createContext, useContext } from "react";

/**
 * When true, queue list/attempts queries enable TanStack Query refetchInterval
 * as the SSE fallback. Provided once from QueueView — default false elsewhere.
 */
export const QueueRealtimePollingContext = createContext(false);

export function useQueueRealtimePollingEnabled(): boolean {
  return useContext(QueueRealtimePollingContext);
}

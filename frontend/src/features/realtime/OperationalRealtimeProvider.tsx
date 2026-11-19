"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useQueueRealtimeInvalidation } from "@/features/queue/hooks/useQueueRealtimeInvalidation";
import {
  QueueRealtimePollingContext,
  QueueRealtimeStatusContext,
} from "@/features/queue/hooks/QueueRealtimePollingContext";

const OPERATIONAL_PATHS = new Set(["/dashboard", "/queue"]);

/**
 * Owns the single queue event stream for the operational pages. Other pages
 * do not keep an SSE connection open, while Dashboard and Queue share the
 * same invalidation and fallback-polling lifecycle.
 */
export function OperationalRealtimeProvider({
  children,
}: {
  children: ReactNode;
}) {
  const pathname = usePathname();
  const enabled = OPERATIONAL_PATHS.has(pathname ?? "");
  const realtime = useQueueRealtimeInvalidation({ enabled });

  return (
    <QueueRealtimePollingContext.Provider value={realtime.pollingEnabled}>
      <QueueRealtimeStatusContext.Provider value={realtime.status}>
        {children}
      </QueueRealtimeStatusContext.Provider>
    </QueueRealtimePollingContext.Provider>
  );
}

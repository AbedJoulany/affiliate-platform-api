"use client";

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDashboardOverview } from "../api/dashboard.api";
import { useActiveWorkspaceId, workspaceScopedQueryKey } from "@/lib/workspace";
import { createQueuePollIntervalSelector } from "@/features/queue/lib/queue-polling";
import { useQueueRealtimePollingEnabled } from "@/features/queue/hooks/QueueRealtimePollingContext";

export const dashboardKey = (workspaceId: string) =>
  workspaceScopedQueryKey("dashboard", workspaceId);

export function useDashboard() {
  const workspaceId = useActiveWorkspaceId();
  const pollingEnabled = useQueueRealtimePollingEnabled();
  const refetchInterval = useMemo(
    () => (pollingEnabled ? createQueuePollIntervalSelector() : false),
    [pollingEnabled],
  );
  const query = useQuery({
    queryKey: workspaceId
      ? dashboardKey(workspaceId)
      : (["dashboard", "none"] as const),
    queryFn: getDashboardOverview,
    enabled: Boolean(workspaceId),
    retry: false,
    refetchInterval,
  });

  useDashboardReportingRollover(
    workspaceId,
    query.data?.reporting.day_end_utc ?? null,
    query.refetch,
  );

  return query;
}

export function useDashboardReportingRollover(
  workspaceId: string | null,
  dayEndUtc: string | null,
  refetch: () => Promise<unknown>,
) {
  useEffect(() => {
    if (!workspaceId || !dayEndUtc) return;
    const boundary = Date.parse(dayEndUtc);
    if (!Number.isFinite(boundary)) return;

    let timer: ReturnType<typeof setTimeout> | null = null;
    const refreshIfDue = () => {
      if (Date.now() < boundary) return;
      if (
        typeof document === "undefined" ||
        document.visibilityState !== "hidden"
      ) {
        void refetch();
      }
    };

    const delay = Math.max(1_000, boundary - Date.now());
    timer = setTimeout(refreshIfDue, delay);
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refreshIfDue();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [dayEndUtc, refetch, workspaceId]);
}

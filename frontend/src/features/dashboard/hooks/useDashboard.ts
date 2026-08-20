"use client";

import { useQuery } from "@tanstack/react-query";
import { getDashboardOverview } from "../api/dashboard.api";
import { useActiveWorkspaceId, workspaceScopedQueryKey } from "@/lib/workspace";

export const dashboardKey = (workspaceId: string) =>
  workspaceScopedQueryKey("dashboard", workspaceId);

export function useDashboard() {
  const workspaceId = useActiveWorkspaceId();
  return useQuery({
    queryKey: workspaceId ? dashboardKey(workspaceId) : (["dashboard", "none"] as const),
    queryFn: getDashboardOverview,
    enabled: Boolean(workspaceId),
    retry: false,
  });
}

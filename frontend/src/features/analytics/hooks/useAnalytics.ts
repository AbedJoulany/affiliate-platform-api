"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getActiveCampaigns,
  getAnalyticsOverview,
  getCampaignFunnel,
} from "../api/analytics.api";
import type { AnalyticsRange } from "../types/api";
import { useActiveWorkspaceId, workspaceScopedQueryKey } from "@/lib/workspace";

export const analyticsOverviewKey = (workspaceId: string, range: AnalyticsRange) =>
  workspaceScopedQueryKey("analytics", workspaceId, "overview", range.from, range.to);

export const analyticsFunnelKey = (
  workspaceId: string,
  campaignId: string,
  range: AnalyticsRange,
) =>
  workspaceScopedQueryKey(
    "analytics",
    workspaceId,
    "funnel",
    campaignId,
    range.from,
    range.to,
  );

export function useAnalyticsOverview(range: AnalyticsRange) {
  const workspaceId = useActiveWorkspaceId();
  return useQuery({
    queryKey: workspaceId
      ? analyticsOverviewKey(workspaceId, range)
      : (["analytics", "none", "overview"] as const),
    queryFn: () => getAnalyticsOverview(range),
    enabled: Boolean(workspaceId),
    retry: false,
  });
}

export function useCampaignFunnel(campaignId: string | null, range: AnalyticsRange) {
  const workspaceId = useActiveWorkspaceId();
  return useQuery({
    queryKey:
      workspaceId && campaignId
        ? analyticsFunnelKey(workspaceId, campaignId, range)
        : (["analytics", workspaceId ?? "none", "funnel", campaignId ?? "idle"] as const),
    queryFn: () => getCampaignFunnel(campaignId as string, range),
    enabled: Boolean(workspaceId) && Boolean(campaignId),
    retry: false,
  });
}

export function useActiveCampaigns() {
  const workspaceId = useActiveWorkspaceId();
  return useQuery({
    queryKey: workspaceId
      ? workspaceScopedQueryKey("analytics", workspaceId, "campaigns")
      : (["analytics", "none", "campaigns"] as const),
    queryFn: getActiveCampaigns,
    enabled: Boolean(workspaceId),
    retry: false,
  });
}

import { apiClient } from "@/services/api-client";
import type {
  AnalyticsCampaignFunnel,
  AnalyticsOverview,
  AnalyticsRange,
  CampaignOption,
} from "../types/api";

export async function getAnalyticsOverview(
  range: AnalyticsRange,
): Promise<AnalyticsOverview> {
  const { data } = await apiClient.get<AnalyticsOverview>("/analytics/overview", {
    params: { from: range.from, to: range.to },
  });
  return data;
}

export async function getCampaignFunnel(
  campaignId: string,
  range: AnalyticsRange,
): Promise<AnalyticsCampaignFunnel> {
  const { data } = await apiClient.get<AnalyticsCampaignFunnel>(
    `/analytics/campaigns/${campaignId}/funnel`,
    { params: { from: range.from, to: range.to } },
  );
  return data;
}

export async function getActiveCampaigns(): Promise<CampaignOption[]> {
  const { data } = await apiClient.get<CampaignOption[]>("/campaigns/active");
  return data;
}

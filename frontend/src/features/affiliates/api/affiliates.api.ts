import { apiClient } from "@/services/api-client";

export type AffiliateCampaignJoinInput = {
  campaign_id: string;
};

export type AffiliateCampaignRead = {
  id: string;
  affiliate_id: string;
  campaign_id: string;
  tracking_link: string;
  created_at: string;
  updated_at: string;
};

export async function joinCampaign(
  input: AffiliateCampaignJoinInput,
): Promise<AffiliateCampaignRead> {
  const { data } = await apiClient.post<AffiliateCampaignRead>(
    "/affiliates/join-campaign",
    { campaign_id: input.campaign_id },
  );
  return data;
}

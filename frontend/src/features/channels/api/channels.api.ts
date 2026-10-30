import { apiClient } from "@/services/api-client";
import type {
  Channel,
  ChannelCreate,
  ChannelListResponse,
  FacebookPage,
  FacebookPageCreate,
  FacebookPageListResponse,
} from "../types/api";

export async function getChannels(): Promise<ChannelListResponse> {
  const { data } = await apiClient.get<ChannelListResponse>("/channels");
  return data;
}

export async function createChannel(input: ChannelCreate): Promise<Channel> {
  const { data } = await apiClient.post<Channel>("/channels", input);
  return data;
}

export async function updateChannel(id: string, input: Partial<ChannelCreate>): Promise<Channel> {
  const { data } = await apiClient.put<Channel>(`/channels/${id}`, input);
  return data;
}

export async function refreshChannelPermissions(id: string): Promise<Channel> {
  const { data } = await apiClient.post<Channel>(`/channels/${id}/refresh-permissions`);
  return data;
}

export async function getFacebookPages(): Promise<FacebookPageListResponse> {
  const { data } = await apiClient.get<FacebookPageListResponse>("/facebook/pages");
  return data;
}

export async function createFacebookPage(input: FacebookPageCreate): Promise<FacebookPage> {
  const { data } = await apiClient.post<FacebookPage>("/facebook/pages", input);
  return data;
}

export async function validateFacebookPage(id: string): Promise<FacebookPage> {
  const { data } = await apiClient.post<FacebookPage>(`/facebook/pages/${id}/validate`);
  return data;
}

export async function updateFacebookPage(
  id: string,
  input: { access_token?: string; token_expires_at?: string; is_active?: boolean },
): Promise<FacebookPage> {
  const { data } = await apiClient.patch<FacebookPage>(`/facebook/pages/${id}`, input);
  return data;
}

export async function deleteFacebookPage(id: string): Promise<void> {
  await apiClient.delete(`/facebook/pages/${id}`);
}

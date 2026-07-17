import { apiClient } from "@/services/api-client";
import type { Channel, ChannelCreate, ChannelListResponse } from "../types/api";

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

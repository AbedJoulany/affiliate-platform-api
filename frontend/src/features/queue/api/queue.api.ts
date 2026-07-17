import { apiClient } from "@/services/api-client";
import type {
  PublishQueueResponse,
  QueueCreate,
  QueueItem,
  QueueListResponse,
  QueueStatus,
} from "../types/api";

export async function getQueue(status?: QueueStatus): Promise<QueueListResponse> {
  const { data } = await apiClient.get<QueueListResponse>("/queues", { params: { status } });
  return data;
}

export async function createQueueItem(input: QueueCreate): Promise<QueueItem> {
  const { data } = await apiClient.post<QueueItem>("/queues", input);
  return data;
}

export async function publishQueueItem(id: string): Promise<PublishQueueResponse> {
  const { data } = await apiClient.post<PublishQueueResponse>(`/queues/${id}/publish`);
  return data;
}

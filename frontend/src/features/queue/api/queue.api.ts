import { apiClient } from "@/services/api-client";
import type {
  PublishQueueResponse,
  QueueCreate,
  QueueItem,
  QueueListResponse,
  QueuePublishAttemptListResponse,
  QueueStatus,
  QueueUpdate,
} from "../types/api";

export async function getQueue(
  status?: QueueStatus,
  limit = 20,
  skip = 0,
): Promise<QueueListResponse> {
  const { data } = await apiClient.get<QueueListResponse>("/queues", {
    params: { status, limit, skip },
  });
  return data;
}

export async function getQueueItem(id: string): Promise<QueueItem> {
  const { data } = await apiClient.get<QueueItem>(`/queues/${id}`);
  return data;
}

export async function getQueuePublishAttempts(
  id: string,
): Promise<QueuePublishAttemptListResponse> {
  const { data } = await apiClient.get<QueuePublishAttemptListResponse>(
    `/queues/${id}/attempts`,
  );
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

export async function updateQueueItem(
  id: string,
  input: QueueUpdate,
): Promise<QueueItem> {
  const { data } = await apiClient.patch<QueueItem>(`/queues/${id}`, input);
  return data;
}

export async function deleteQueueItem(id: string): Promise<void> {
  await apiClient.delete(`/queues/${id}`);
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createQueueItem, getQueue, publishQueueItem } from "../api/queue.api";
import type { QueueStatus } from "../types/api";

const queueKey = ["queue"] as const;

export function useQueue(status?: QueueStatus) {
  return useQuery({ queryKey: [...queueKey, status], queryFn: () => getQueue(status) });
}

export function useCreateQueueItem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createQueueItem,
    onSuccess: () => client.invalidateQueries({ queryKey: queueKey }),
  });
}

export function usePublishQueueItem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: publishQueueItem,
    onSuccess: () => client.invalidateQueries({ queryKey: queueKey }),
  });
}

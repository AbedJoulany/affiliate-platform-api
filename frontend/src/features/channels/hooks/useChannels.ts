"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createChannel, getChannels, updateChannel } from "../api/channels.api";
import type { Channel, ChannelCreate } from "../types/api";
import type { ApiError } from "@/services/api-client";

const channelKey = ["channels"] as const;

export function useChannels() {
  return useQuery({ queryKey: channelKey, queryFn: getChannels });
}

export function useCreateChannel() {
  const client = useQueryClient();
  return useMutation<Channel, ApiError, ChannelCreate>({
    mutationFn: createChannel,
    onSuccess: () => client.invalidateQueries({ queryKey: channelKey }),
  });
}

export function useUpdateChannel() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: { is_active: boolean } }) =>
      updateChannel(id, input),
    onSuccess: () => client.invalidateQueries({ queryKey: channelKey }),
  });
}

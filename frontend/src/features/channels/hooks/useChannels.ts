"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createChannel, getChannels, updateChannel } from "../api/channels.api";
import type { Channel, ChannelCreate } from "../types/api";
import { useActiveWorkspaceId, workspaceScopedQueryKey } from "@/lib/workspace";
import type { ApiError } from "@/services/api-client";

export const channelKey = (workspaceId: string) =>
  workspaceScopedQueryKey("channels", workspaceId);

export function useChannels() {
  const workspaceId = useActiveWorkspaceId();
  return useQuery({
    queryKey: workspaceId ? channelKey(workspaceId) : (["channels", "none"] as const),
    queryFn: getChannels,
    enabled: Boolean(workspaceId),
  });
}

export function useCreateChannel() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation<Channel, ApiError, ChannelCreate>({
    mutationFn: createChannel,
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: channelKey(workspaceId) });
    },
  });
}

export function useUpdateChannel() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: { is_active: boolean } }) =>
      updateChannel(id, input),
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: channelKey(workspaceId) });
    },
  });
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createChannel,
  getChannels,
  refreshChannelPermissions,
  updateChannel,
  createFacebookPage,
  deleteFacebookPage,
  getFacebookPages,
  updateFacebookPage,
  validateFacebookPage,
} from "../api/channels.api";
import type { Channel, ChannelCreate, FacebookPage, FacebookPageCreate } from "../types/api";
import { useActiveWorkspaceId, workspaceScopedQueryKey } from "@/lib/workspace";
import type { ApiError } from "@/services/api-client";

export const channelKey = (workspaceId: string) =>
  workspaceScopedQueryKey("channels", workspaceId);

export const facebookPageKey = (workspaceId: string) =>
  workspaceScopedQueryKey("facebook", workspaceId);

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

export function useRefreshChannelPermissions() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: refreshChannelPermissions,
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: channelKey(workspaceId) });
    },
  });
}

export function useFacebookPages() {
  const workspaceId = useActiveWorkspaceId();
  return useQuery({
    queryKey: workspaceId ? facebookPageKey(workspaceId) : (["facebook", "none"] as const),
    queryFn: getFacebookPages,
    enabled: Boolean(workspaceId),
  });
}

export function useCreateFacebookPage() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation<FacebookPage, ApiError, FacebookPageCreate>({
    mutationFn: createFacebookPage,
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: facebookPageKey(workspaceId) });
    },
  });
}

export function useValidateFacebookPage() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: validateFacebookPage,
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: facebookPageKey(workspaceId) });
    },
  });
}

export function useUpdateFacebookPage() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: { access_token?: string; is_active?: boolean } }) =>
      updateFacebookPage(id, input),
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: facebookPageKey(workspaceId) });
    },
  });
}

export function useDeleteFacebookPage() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation({
    mutationFn: deleteFacebookPage,
    onSuccess: () => {
      if (workspaceId) void client.invalidateQueries({ queryKey: facebookPageKey(workspaceId) });
    },
  });
}

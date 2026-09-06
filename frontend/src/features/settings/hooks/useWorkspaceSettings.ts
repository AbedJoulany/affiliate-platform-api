"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getWorkspaceSettings, patchWorkspaceSettings } from "../api/settings.api";
import type { WorkspaceSettings, WorkspaceSettingsPatch } from "../types/api";
import { useActiveWorkspaceId, workspaceScopedQueryKey } from "@/lib/workspace";
import type { ApiError } from "@/services/api-client";

export const workspaceSettingsKey = (workspaceId: string) =>
  workspaceScopedQueryKey("workspace-settings", workspaceId);

export function useWorkspaceSettings() {
  const workspaceId = useActiveWorkspaceId();
  return useQuery({
    queryKey: workspaceId
      ? workspaceSettingsKey(workspaceId)
      : (["workspace-settings", "none"] as const),
    queryFn: getWorkspaceSettings,
    enabled: Boolean(workspaceId),
    retry: false,
  });
}

export function usePatchWorkspaceSettings() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation<WorkspaceSettings, ApiError, WorkspaceSettingsPatch>({
    mutationFn: patchWorkspaceSettings,
    onSuccess: (data) => {
      if (workspaceId) {
        client.setQueryData(workspaceSettingsKey(workspaceId), data);
      }
    },
  });
}

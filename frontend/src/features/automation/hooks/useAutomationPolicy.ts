"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useActiveWorkspaceId, workspaceScopedQueryKey } from "@/lib/workspace";
import type { ApiError } from "@/services/api-client";
import { getAutomationPolicy, patchAutomationPolicy } from "../api/automation.api";
import type { AutomationPolicy, AutomationPolicyPatch } from "../types/api";

export const automationPolicyKey = (workspaceId: string) =>
  workspaceScopedQueryKey("automation", workspaceId);

export function useAutomationPolicy() {
  const workspaceId = useActiveWorkspaceId();
  return useQuery({
    queryKey: workspaceId
      ? automationPolicyKey(workspaceId)
      : (["automation", "none"] as const),
    queryFn: ({ queryKey }) => getAutomationPolicy(queryKey[1] as string),
    enabled: Boolean(workspaceId),
    retry: false,
  });
}

export function usePatchAutomationPolicy() {
  const client = useQueryClient();
  return useMutation<
    AutomationPolicy,
    ApiError,
    { workspaceId: string; patch: AutomationPolicyPatch }
  >({
    mutationFn: ({ workspaceId: targetWorkspaceId, patch }) =>
      patchAutomationPolicy(targetWorkspaceId, patch),
    onSuccess: (data, variables) => {
      if (data.workspace_id === variables.workspaceId) {
        client.setQueryData(automationPolicyKey(variables.workspaceId), data);
      }
    },
  });
}

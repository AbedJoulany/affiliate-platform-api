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
    queryFn: getAutomationPolicy,
    enabled: Boolean(workspaceId),
    retry: false,
  });
}

export function usePatchAutomationPolicy() {
  const client = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  return useMutation<AutomationPolicy, ApiError, AutomationPolicyPatch>({
    mutationFn: patchAutomationPolicy,
    onSuccess: (data) => {
      if (workspaceId) {
        client.setQueryData(automationPolicyKey(workspaceId), data);
      }
    },
  });
}

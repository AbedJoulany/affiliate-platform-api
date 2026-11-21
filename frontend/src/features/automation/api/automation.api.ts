import { apiClient } from "@/services/api-client";
import type { AutomationPolicy, AutomationPolicyPatch } from "../types/api";

function parseAutomationPolicy(data: unknown): AutomationPolicy {
  if (typeof data !== "object" || data === null) {
    throw new Error("استجابة إعدادات الأتمتة غير صالحة.");
  }
  const value = data as Record<string, unknown>;
  if (
    typeof value.workspace_id !== "string" ||
    typeof value.revision !== "number" ||
    typeof value.enabled !== "boolean" ||
    value.execution_available !== false ||
    typeof value.execution_state !== "string" ||
    !("destination" in value) ||
    typeof value.discovery !== "object" ||
    value.discovery === null ||
    typeof value.schedule !== "object" ||
    value.schedule === null ||
    typeof value.content !== "object" ||
    value.content === null ||
    !Array.isArray(value.warnings)
  ) {
    throw new Error("استجابة إعدادات الأتمتة غير صالحة.");
  }
  return data as AutomationPolicy;
}

export async function getAutomationPolicy(workspaceId: string): Promise<AutomationPolicy> {
  const { data } = await apiClient.get<AutomationPolicy>("/automation/config", {
    workspaceId,
  });
  return parseAutomationPolicy(data);
}

export async function patchAutomationPolicy(
  workspaceId: string,
  input: AutomationPolicyPatch,
): Promise<AutomationPolicy> {
  const { data } = await apiClient.patch<AutomationPolicy>(
    "/automation/config",
    input,
    { workspaceId },
  );
  return parseAutomationPolicy(data);
}

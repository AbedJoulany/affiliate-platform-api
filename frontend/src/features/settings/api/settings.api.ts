import { apiClient } from "@/services/api-client";
import type { WorkspaceSettings, WorkspaceSettingsPatch } from "../types/api";

export async function getWorkspaceSettings(): Promise<WorkspaceSettings> {
  const { data } = await apiClient.get<WorkspaceSettings>("/workspace-settings");
  return data;
}

export async function patchWorkspaceSettings(
  input: WorkspaceSettingsPatch,
): Promise<WorkspaceSettings> {
  const { data } = await apiClient.patch<WorkspaceSettings>("/workspace-settings", input);
  return data;
}

import { apiClient } from "@/services/api-client";
import type { DashboardOverview } from "../types/api";

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await apiClient.get<DashboardOverview>("/dashboard");
  return data;
}

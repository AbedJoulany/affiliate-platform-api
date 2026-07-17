import { apiClient } from "@/services/api-client";
import type { CategoryListResponse, ReadinessResponse } from "../types/api";

export async function getCategories(): Promise<CategoryListResponse> {
  const { data } = await apiClient.get<CategoryListResponse>("/aliexpress/categories");
  return data;
}

export async function getPlatformReadiness(): Promise<ReadinessResponse> {
  const apiBase = new URL(
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  );
  const { data } = await apiClient.get<ReadinessResponse>(
    new URL("/ready", apiBase.origin).toString(),
    { validateStatus: (status) => status === 200 || status === 503 },
  );
  return data;
}

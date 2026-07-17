import { apiClient } from "@/services/api-client";
import type { GenerateContentInput, GenerateContentResponse } from "../types/api";

export async function generateContent(
  input: GenerateContentInput,
): Promise<GenerateContentResponse> {
  const { data } = await apiClient.post<GenerateContentResponse>("/ai-content/generate", input);
  return data;
}

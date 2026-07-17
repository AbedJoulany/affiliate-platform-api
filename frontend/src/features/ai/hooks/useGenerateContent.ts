"use client";

import { useMutation } from "@tanstack/react-query";
import { generateContent } from "../api/ai.api";
import type { GenerateContentInput, GenerateContentResponse } from "../types/api";
import type { ApiError } from "@/services/api-client";

export function useGenerateContent() {
  return useMutation<GenerateContentResponse, ApiError, GenerateContentInput>({
    mutationFn: generateContent,
  });
}

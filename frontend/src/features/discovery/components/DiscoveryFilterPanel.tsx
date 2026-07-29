import type { DiscoveryParams } from "../types/api";

/** Shared draft validation for Discovery run actions. */
export function validateDiscoveryDraft(params: DiscoveryParams): string | null {
  const mode = params.mode ?? "hot";
  if (mode === "category" && !params.category_id?.trim()) return "اختر فئة قبل التشغيل.";
  return null;
}

export type { DiscoveryMode } from "../types/api";

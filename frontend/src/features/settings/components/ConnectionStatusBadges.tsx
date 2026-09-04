"use client";

import { Badge } from "@/components/ui/primitives";
import type { ProviderConnectionStatus, SettingsSection } from "../types/api";

const LABELS: Record<keyof ProviderConnectionStatus, string> = {
  aliexpress: "AliExpress",
  telegram_bot: "بوت Telegram",
  openai: "OpenAI",
  gemini: "Gemini",
  image_search: "البحث بالصورة",
};

const SECTION_KEYS: Record<SettingsSection, ReadonlyArray<keyof ProviderConnectionStatus>> = {
  general: [],
  aliexpress: ["aliexpress", "image_search"],
  ai: ["openai", "gemini"],
  telegram: ["telegram_bot"],
  discovery: ["aliexpress", "image_search"],
  scheduling: [],
};

export function ConnectionStatusBadges({
  section,
  connections,
}: {
  section: SettingsSection;
  connections: ProviderConnectionStatus;
}) {
  const keys = SECTION_KEYS[section];
  if (keys.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {keys.map((key) => (
        <Badge key={key} tone={connections[key] ? "success" : "warning"}>
          {LABELS[key]}: {connections[key] ? "متصل" : "غير متصل"}
        </Badge>
      ))}
    </div>
  );
}

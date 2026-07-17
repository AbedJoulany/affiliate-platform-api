"use client";

import { cn } from "@/lib/utils";
import type { DiscoveryMode } from "../types/api";

const INTENTS: ReadonlyArray<{ id: DiscoveryMode; label: string }> = [
  { id: "hot", label: "الأكثر رواجًا" },
  { id: "trending", label: "الصاعدة" },
  { id: "deals", label: "العروض" },
  { id: "category", label: "فئة" },
  { id: "general", label: "كلمات مفتاحية" },
];

export function DiscoveryIntentTabs({
  value,
  onChange,
}: {
  value: DiscoveryMode;
  onChange: (mode: DiscoveryMode) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2" role="tablist" aria-label="مصدر الاكتشاف">
      {INTENTS.map((intent) => (
        <button
          key={intent.id}
          type="button"
          role="tab"
          aria-selected={value === intent.id}
          className={cn(
            "rounded-md border px-3 py-2 text-sm transition",
            value === intent.id
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-surface hover:bg-muted",
          )}
          onClick={() => onChange(intent.id)}
        >
          {intent.label}
        </button>
      ))}
      {/* Extension: multiple affiliate sources / networks */}
    </div>
  );
}

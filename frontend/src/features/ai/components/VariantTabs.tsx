"use client";

import { Button } from "@/components/ui/primitives";
import type { ContentVariant } from "../types/session";

export function VariantTabs({
  variants,
  activeVariantId,
  onActivate,
  onCompare,
  onRestorePrevious,
}: {
  variants: ContentVariant[];
  activeVariantId: string | null;
  onActivate: (id: string) => void;
  onCompare: () => void;
  onRestorePrevious: () => void;
}) {
  if (variants.length === 0) return null;

  const activeIndex = variants.findIndex((item) => item.id === activeVariantId);
  const canRestore = activeIndex > 0;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="نسخ المحتوى">
        {variants.map((variant) => {
          const active = variant.id === activeVariantId;
          return (
            <button
              key={variant.id}
              type="button"
              role="tab"
              aria-selected={active}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                active
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
              onClick={() => onActivate(variant.id)}
            >
              النسخة {variant.index}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          className="h-9"
          disabled={variants.length < 2}
          onClick={onCompare}
        >
          مقارنة النسخ
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-9"
          disabled={!canRestore}
          onClick={onRestorePrevious}
        >
          استعادة النسخة السابقة
        </Button>
      </div>
    </div>
  );
}

"use client";

import { Chip } from "@/components/ui/primitives";
import { CONTENT_TYPE_OPTIONS, type ContentSession } from "../types/session";
import type { ContentType } from "../types/api";

export function ContentTypeScroller({
  value,
  onChange,
}: {
  value: ContentSession["config"]["contentType"];
  onChange: (value: ContentType) => void;
}) {
  return (
    <div>
      <p className="mb-1.5 text-sm">نوع المحتوى</p>
      <div className="flex max-h-28 flex-wrap gap-2 overflow-y-auto rounded-md border border-border bg-muted/20 p-2">
        {CONTENT_TYPE_OPTIONS.map((option) => (
          <Chip
            key={option.value}
            active={value === option.value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </Chip>
        ))}
      </div>
    </div>
  );
}

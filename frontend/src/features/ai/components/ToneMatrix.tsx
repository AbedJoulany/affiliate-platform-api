"use client";

import { Chip } from "@/components/ui/primitives";
import type { ToneProfile } from "../types/api";
import { TONE_OPTIONS } from "../types/session";

export function ToneMatrix({
  value,
  onChange,
}: {
  value: ToneProfile;
  onChange: (value: ToneProfile) => void;
}) {
  return (
    <div>
      <p className="mb-1.5 text-sm">نبرة المحتوى</p>
      <div className="flex flex-wrap gap-2">
        {TONE_OPTIONS.map((option) => (
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

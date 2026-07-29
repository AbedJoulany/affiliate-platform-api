"use client";

import { Chip, Collapsible } from "@/components/ui/primitives";
import type { InstructionModifier } from "../types/api";
import { MODIFIER_OPTIONS } from "../types/session";

export function AiSuggestionsPanel({
  open,
  activeModifiers,
  onToggleOpen,
  onToggleModifier,
  onApplyVariant,
  applying,
}: {
  open: boolean;
  activeModifiers: InstructionModifier[];
  onToggleOpen: () => void;
  onToggleModifier: (modifier: InstructionModifier) => void;
  onApplyVariant: () => void;
  applying: boolean;
}) {
  return (
    <Collapsible
      open={open}
      title="اقتراحات الذكاء الاصطناعي"
      onToggle={onToggleOpen}
      className="bg-surface"
    >
      <p className="mb-3 text-xs text-muted-foreground">
        فعّل التعديلات ثم ولّد نسخة بديلة لتطبيقها على الجلسة دون إعادة كتابة يدوية.
      </p>
      <div className="flex flex-wrap gap-2">
        {MODIFIER_OPTIONS.map((option) => {
          const active = activeModifiers.includes(option.value);
          return (
            <Chip
              key={option.value}
              active={active}
              onClick={() => onToggleModifier(option.value)}
            >
              {option.label} {active ? "✓" : "✕"}
            </Chip>
          );
        })}
      </div>
      <button
        type="button"
        className="mt-4 text-sm font-medium text-primary underline disabled:opacity-50"
        disabled={applying || activeModifiers.length === 0}
        onClick={onApplyVariant}
      >
        تطبيق الاقتراحات كنسخة بديلة
      </button>
    </Collapsible>
  );
}

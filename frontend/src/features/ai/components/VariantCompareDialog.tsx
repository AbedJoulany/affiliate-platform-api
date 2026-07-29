"use client";

import { Button } from "@/components/ui/primitives";
import type { ContentVariant } from "../types/session";

export function VariantCompareDialog({
  open,
  left,
  right,
  onClose,
}: {
  open: boolean;
  left: ContentVariant | null;
  right: ContentVariant | null;
  onClose: () => void;
}) {
  if (!open || !left || !right) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        className="max-h-[85vh] w-full max-w-5xl overflow-hidden rounded-xl border border-border bg-surface shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-label="مقارنة النسخ"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="font-semibold">مقارنة النسخ</h2>
          <Button type="button" variant="ghost" className="px-2" onClick={onClose}>
            إغلاق
          </Button>
        </div>
        <div className="grid max-h-[calc(85vh-3.5rem)] gap-0 overflow-y-auto md:grid-cols-2">
          <ComparePane title={`النسخة ${left.index}`} content={left.content} />
          <ComparePane title={`النسخة ${right.index}`} content={right.content} />
        </div>
      </div>
    </div>
  );
}

function ComparePane({ title, content }: { title: string; content: string }) {
  return (
    <section className="border-b border-border p-4 md:border-b-0 md:border-e">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      <pre className="whitespace-pre-wrap text-sm leading-7 text-foreground/90" dir="rtl">
        {content}
      </pre>
    </section>
  );
}

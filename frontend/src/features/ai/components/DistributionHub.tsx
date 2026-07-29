"use client";

import { useState } from "react";
import { RotateCcw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/primitives";

export function DistributionHub({
  disabled,
  busy,
  generating,
  canGenerate,
  hasVariants,
  onGenerate,
  onPublishNow,
  onAddToQueue,
  onSaveDraft,
  onRegenerate,
  onReset,
  onCopy,
  onExport,
}: {
  disabled: boolean;
  busy: boolean;
  generating: boolean;
  canGenerate: boolean;
  hasVariants: boolean;
  onGenerate: () => void;
  onPublishNow: () => void;
  onAddToQueue: () => void;
  onSaveDraft: () => void;
  onRegenerate: () => void;
  onReset: () => void;
  onCopy: () => void;
  onExport: (format: "txt" | "md" | "html") => void;
}) {
  const [exportOpen, setExportOpen] = useState(false);

  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <Button
          type="button"
          disabled={!canGenerate || generating}
          loading={generating && !hasVariants}
          onClick={onGenerate}
        >
          <Sparkles className="size-4" />
          إنشاء المحتوى
        </Button>
        <Button
          type="button"
          disabled={disabled || busy}
          loading={busy}
          onClick={onPublishNow}
        >
          نشر الآن
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={disabled || busy}
          loading={busy}
          onClick={onAddToQueue}
        >
          إضافة إلى جدولة النشر
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={disabled || busy}
          loading={busy}
          onClick={onSaveDraft}
        >
          حفظ كمسودة
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!canGenerate || generating || !hasVariants}
          loading={generating && hasVariants}
          onClick={onRegenerate}
        >
          توليد نسخة بديلة
        </Button>
        <Button
          type="button"
          variant="outline"
          className="border-amber-500/40 text-amber-800 hover:bg-amber-500/10 dark:text-amber-300"
          onClick={onReset}
        >
          <RotateCcw className="size-4" />
          إعادة تعيين
        </Button>
      </div>

      <div className="mt-2 flex flex-wrap gap-2">
        <Button type="button" variant="ghost" className="h-9" disabled={disabled} onClick={onCopy}>
          نسخ النص الحالي
        </Button>
        <div className="relative">
          <Button
            type="button"
            variant="ghost"
            className="h-9"
            disabled={disabled}
            onClick={() => setExportOpen((prev) => !prev)}
          >
            تصدير المحتوى
          </Button>
          {exportOpen ? (
            <div className="absolute bottom-full z-20 mb-1 min-w-[8rem] rounded-md border border-border bg-surface p-1 shadow-lg">
              {(["txt", "md", "html"] as const).map((format) => (
                <button
                  key={format}
                  type="button"
                  className="block w-full rounded px-3 py-2 text-start text-sm hover:bg-muted"
                  onClick={() => {
                    onExport(format);
                    setExportOpen(false);
                  }}
                >
                  .{format}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

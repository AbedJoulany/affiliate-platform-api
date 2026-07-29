"use client";

import {
  CONTENT_TYPE_OPTIONS,
  LANGUAGE_OPTIONS,
  LENGTH_OPTIONS,
  TONE_OPTIONS,
  type ContentSession,
} from "../types/session";

function labelOf<T extends string>(
  options: ReadonlyArray<{ value: T; label: string }>,
  value: T,
): string {
  return options.find((item) => item.value === value)?.label ?? value;
}

export function PromptPipelinePreview({ session }: { session: ContentSession }) {
  const product =
    session.productContext.sourceType === "product"
      ? session.productContext.productLabel || session.productContext.productId || "منتج"
      : session.productContext.url?.trim()
        ? "رابط AliExpress"
        : "بدون مصدر";

  const steps = [
    { key: "product", label: "المنتج", value: product },
    {
      key: "platform",
      label: "المنصة",
      value: labelOf(CONTENT_TYPE_OPTIONS, session.config.contentType),
    },
    { key: "tone", label: "النبرة", value: labelOf(TONE_OPTIONS, session.config.tone) },
    {
      key: "language",
      label: "اللغة",
      value: labelOf(LANGUAGE_OPTIONS, session.config.language),
    },
    {
      key: "length",
      label: "الطول",
      value: labelOf(LENGTH_OPTIONS, session.config.length),
    },
  ] as const;

  return (
    <div
      className="rounded-md border border-dashed border-border bg-muted/30 px-3 py-2"
      aria-label="ملخص إعدادات المحتوى"
    >
      <p className="mb-2 text-[11px] text-muted-foreground">معاينة الإعدادات قبل التوليد</p>
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        {steps.map((step, index) => (
          <div key={step.key} className="flex items-center gap-1.5">
            {index > 0 ? (
              <span className="text-muted-foreground" aria-hidden>
                ←
              </span>
            ) : null}
            <span className="rounded-md bg-surface px-2 py-1 font-medium">
              <span className="text-muted-foreground">{step.label}: </span>
              {step.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

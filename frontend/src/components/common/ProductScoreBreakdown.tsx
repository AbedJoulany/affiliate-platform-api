"use client";

import { Badge } from "@/components/ui/primitives";
import {
  getProductScoreQuality,
  type ProductScoreBreakdown as ProductScoreBreakdownModel,
} from "@/lib/product-score";

export function ProductScoreBreakdown({
  breakdown,
  compact = false,
}: {
  breakdown: ProductScoreBreakdownModel;
  compact?: boolean;
}) {
  const quality = getProductScoreQuality(breakdown.total);
  const meterWidth = Math.min(100, Math.max(0, breakdown.total));

  return (
    <div className={compact ? "space-y-3" : "space-y-4"} dir="rtl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">تفسير نتيجة AI</p>
          {!compact ? (
            <p className="mt-1 text-xs text-muted-foreground">
              النتيجة النهائية تأتي من الخادم. الأوزان أدناه للإيضاح فقط
              {breakdown.source === "documented_weights"
                ? " (40% تقييم · 30% طلبات · 20% خصم · 10% معايير أخرى)."
                : "."}
            </p>
          ) : null}
        </div>
        <div className="text-end">
          <p className="text-2xl font-semibold leading-none tabular-nums">
            {Math.round(breakdown.total)}
          </p>
          <Badge tone={quality.tone} className="mt-1">
            {quality.label}
          </Badge>
        </div>
      </div>

      <div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width]"
            style={{ width: `${meterWidth}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
          <span>0</span>
          <span>55</span>
          <span>70</span>
          <span>85</span>
          <span>100</span>
        </div>
      </div>

      <ul className="space-y-2">
        {breakdown.factors.map((factor) => (
          <li key={factor.key} className="rounded-md bg-muted/50 p-2.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">{factor.label}</span>
              <span className="text-muted-foreground">{factor.weightPercent}%</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground" dir="ltr">
              {factor.inputLabel}
            </p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-background">
              <div
                className="h-full rounded-full bg-primary/80"
                style={{ width: `${factor.weightPercent}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

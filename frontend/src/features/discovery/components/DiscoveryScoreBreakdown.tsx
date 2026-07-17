"use client";

import type { ScoreBreakdown } from "../types/api";

export function DiscoveryScoreBreakdown({ breakdown }: { breakdown: ScoreBreakdown }) {
  return (
    <div className="space-y-3" dir="rtl">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">تفسير نتيجة AI</p>
        <p className="text-lg font-semibold tabular-nums">{breakdown.total.toFixed(2)}</p>
      </div>
      <p className="text-xs text-muted-foreground">
        النتيجة النهائية تأتي من الخادم. الأوزان أدناه للإيضاح فقط
        {breakdown.source === "documented_weights" ? " (40% تقييم · 30% طلبات · 20% خصم · 10% مراجعات)." : "."}
      </p>
      <ul className="space-y-2">
        {breakdown.factors.map((factor) => (
          <li key={factor.key} className="rounded-md bg-muted/50 p-3">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">{factor.label}</span>
              <span className="text-muted-foreground">{factor.weightPercent}%</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground" dir="ltr">
              {factor.inputLabel}
            </p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-background">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${factor.weightPercent}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

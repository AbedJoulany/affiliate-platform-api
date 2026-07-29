"use client";

import type { PerformanceScores } from "../types/session";

const METRICS: ReadonlyArray<{ key: keyof PerformanceScores; label: string }> = [
  { key: "arabic", label: "اللغة العربية" },
  { key: "marketing", label: "الجودة التسويقية" },
  { key: "seo", label: "تحسين محركات البحث" },
  { key: "readability", label: "سهولة القراءة" },
];

function stars(score: number): string {
  const filled = Math.round(score / 20);
  return "★".repeat(filled) + "☆".repeat(Math.max(0, 5 - filled));
}

export function PerformanceScoreBadges({ scores }: { scores: PerformanceScores }) {
  return (
    <div
      className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4"
      aria-label="مؤشرات جودة المحتوى"
    >
      {METRICS.map((metric) => {
        const value = scores[metric.key];
        return (
          <div
            key={metric.key}
            className="rounded-md border border-border bg-muted/30 px-3 py-2"
          >
            <p className="text-[11px] text-muted-foreground">{metric.label}</p>
            <div className="mt-1 flex items-end justify-between gap-2">
              <span className="text-lg font-semibold tabular-nums">{value}</span>
              <span className="text-xs text-amber-600 dark:text-amber-300" aria-hidden>
                {stars(value)}
              </span>
            </div>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-background">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.min(100, value)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

"use client";

import type { DiscoveryRunStatus } from "../types/api";

const statusLabel: Record<DiscoveryRunStatus, string> = {
  idle: "لم يُشغَّل",
  running: "جارٍ التشغيل",
  success: "ناجح",
  error: "فشل",
};

/** Compact KPI strip for header/toolbar — not large dashboard cards. */
export function DiscoveryStats({
  totalDiscovered,
  lastRunStatus,
  pendingReview,
  importedCount,
}: {
  totalDiscovered: number;
  lastRunStatus: DiscoveryRunStatus;
  pendingReview: number;
  importedCount: number;
}) {
  const items = [
    { label: "مكتشف", value: totalDiscovered.toLocaleString("ar") },
    { label: "آخر تشغيل", value: statusLabel[lastRunStatus] },
    { label: "بانتظار المراجعة", value: pendingReview.toLocaleString("ar") },
    { label: "مستورد", value: importedCount.toLocaleString("ar") },
  ] as const;

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm"
      aria-label="ملخص الاكتشاف"
    >
      {items.map((item, index) => (
        <div key={item.label} className="flex items-center gap-2">
          {index > 0 ? <span className="hidden text-border sm:inline" aria-hidden>|</span> : null}
          <span className="text-xs text-muted-foreground">{item.label}</span>
          <span className="font-semibold tabular-nums">{item.value}</span>
        </div>
      ))}
    </div>
  );
}

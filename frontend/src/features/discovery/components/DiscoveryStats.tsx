"use client";

import { Card } from "@/components/ui/primitives";
import type { DiscoveryRunStatus } from "../types/api";

const statusLabel: Record<DiscoveryRunStatus, string> = {
  idle: "لم يُشغَّل",
  running: "جارٍ التشغيل",
  success: "ناجح",
  error: "فشل",
};

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
  const stats = [
    { label: "إجمالي المكتشف", value: totalDiscovered.toLocaleString("ar") },
    { label: "حالة آخر تشغيل", value: statusLabel[lastRunStatus] },
    { label: "بانتظار المراجعة", value: pendingReview.toLocaleString("ar") },
    { label: "تم الاستيراد", value: importedCount.toLocaleString("ar") },
  ] as const;

  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="ملخص الاكتشاف">
      {stats.map((stat) => (
        <Card key={stat.label} className="p-4">
          <p className="text-xs text-muted-foreground">{stat.label}</p>
          <p className="mt-1 text-xl font-semibold tabular-nums">{stat.value}</p>
        </Card>
      ))}
    </section>
  );
}

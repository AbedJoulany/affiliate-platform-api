"use client";

import { formatRate, formatRevenue } from "../lib/range";
import type { AnalyticsOverview } from "../types/api";

export function AnalyticsOverviewCards({
  overview,
}: {
  overview: AnalyticsOverview;
}) {
  const items = [
    { label: "النقرات", value: overview.total_clicks.toLocaleString("ar") },
    { label: "التحويلات", value: overview.total_conversions.toLocaleString("ar") },
    { label: "معدل التحويل", value: formatRate(overview.conversion_rate) },
    { label: "الإيرادات", value: formatRevenue(overview.total_revenue) },
  ];

  return (
    <section
      className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4"
      aria-label="مؤشرات الأداء"
    >
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-lg border border-border bg-surface px-4 py-3"
        >
          <p className="text-xs text-muted-foreground">{item.label}</p>
          <p className="mt-1 text-xl font-semibold tabular-nums">{item.value}</p>
        </div>
      ))}
    </section>
  );
}

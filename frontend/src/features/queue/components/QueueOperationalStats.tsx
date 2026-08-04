"use client";

/** Presentational KPI strip. `failedToday` is computed upstream from backend
 * attempt summaries (client failure map as short-lived rollout fallback). */
export function QueueOperationalStats({
  stats,
}: {
  stats: {
    queued: number;
    scheduled: number;
    publishing: number;
    publishedToday: number;
    failedToday: number;
  };
}) {
  const items = [
    { label: "في الانتظار", value: stats.queued },
    { label: "مجدول", value: stats.scheduled },
    { label: "قيد النشر", value: stats.publishing },
    { label: "نُشر اليوم", value: stats.publishedToday },
    { label: "فشل اليوم", value: stats.failedToday },
  ];

  return (
    <section
      className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5"
      aria-label="إحصاءات عمليات النشر"
    >
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-lg border border-border bg-surface px-4 py-3"
        >
          <p className="text-xs text-muted-foreground">{item.label}</p>
          <p className="mt-1 text-xl font-semibold tabular-nums">
            {item.value.toLocaleString("ar")}
          </p>
        </div>
      ))}
    </section>
  );
}

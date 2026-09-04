"use client";

import { ClickConversionChart } from "./ClickConversionChart";
import { formatRate } from "../lib/range";
import type { AnalyticsCampaignFunnel } from "../types/api";

export function CampaignFunnelChart({
  funnel,
}: {
  funnel: AnalyticsCampaignFunnel;
}) {
  const steps = [
    { label: "النقرات", value: funnel.total_clicks },
    { label: "التحويلات", value: funnel.total_conversions },
    { label: "تحويلات مرتبطة بنقرة", value: funnel.attributed_conversions },
  ];

  return (
    <div className="space-y-4">
      <section
        className="grid gap-2 sm:grid-cols-3"
        aria-label={`قمع الحملة ${funnel.campaign_name}`}
      >
        {steps.map((step) => (
          <div
            key={step.label}
            className="rounded-lg border border-border bg-surface px-4 py-3"
          >
            <p className="text-xs text-muted-foreground">{step.label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">
              {step.value.toLocaleString("ar")}
            </p>
          </div>
        ))}
      </section>
      <p className="text-sm text-muted-foreground">
        معدل التحويل لهذه الحملة: {formatRate(funnel.conversion_rate)}
      </p>
      <ClickConversionChart
        series={funnel.by_day}
        title={`قمع ${funnel.campaign_name} عبر الأيام`}
      />
    </div>
  );
}

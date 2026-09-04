"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { analyticsChartColors } from "../lib/chartTheme";
import type { AnalyticsDayPoint } from "../types/api";

export function ClickConversionChart({
  series,
  title = "النقرات والتحويلات حسب اليوم",
}: {
  series: AnalyticsDayPoint[];
  title?: string;
}) {
  const colors = useMemo(() => analyticsChartColors(), []);
  const data = series.map((point) => ({
    ...point,
    label: point.date.slice(5),
  }));

  return (
    <section
      className="rounded-lg border border-border bg-surface p-4"
      aria-label={title}
    >
      <h2 className="mb-4 font-semibold">{title}</h2>
      <div className="h-72 w-full" dir="ltr">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke={colors.axis} tick={{ fill: colors.axis, fontSize: 12 }} />
            <YAxis allowDecimals={false} stroke={colors.axis} tick={{ fill: colors.axis, fontSize: 12 }} />
            <Tooltip
              contentStyle={{
                background: colors.tooltipBg,
                borderColor: colors.grid,
                color: colors.tooltipFg,
              }}
              labelFormatter={(_label, payload) =>
                payload?.[0]?.payload?.date ? String(payload[0].payload.date) : ""
              }
            />
            <Legend
              formatter={(value) => (value === "clicks" ? "النقرات" : "التحويلات")}
            />
            <Line
              type="monotone"
              dataKey="clicks"
              name="clicks"
              stroke={colors.clicks}
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="conversions"
              name="conversions"
              stroke={colors.conversions}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

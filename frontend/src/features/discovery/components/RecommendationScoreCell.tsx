"use client";

import { useRef, useState } from "react";
import { Badge, Popover } from "@/components/ui/primitives";
import type { DiscoveryProduct, RecommendationScoreFactor } from "../types/api";

const LABELS: Record<RecommendationScoreFactor["key"], string> = {
  rating: "التقييم",
  orders: "الطلبات",
  discount: "الخصم",
  price: "السعر",
  commission: "العمولة",
};

export function RecommendationScoreCell({ product }: { product: DiscoveryProduct }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const score = product.recommendation_score ?? 0;
  const breakdown = product.recommendation_breakdown;

  return (
    <>
      <button
        ref={anchorRef}
        type="button"
        className="flex min-w-[5.5rem] flex-col items-start gap-1 rounded-md p-1 text-start transition hover:bg-muted/60"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((previous) => !previous);
        }}
        onPointerDown={(event) => event.stopPropagation()}
        aria-label={`نتيجة التوصية ${Math.round(score)}`}
      >
        <span className="text-base font-semibold leading-none tabular-nums">{Math.round(score)}</span>
        <Badge tone="info" className="px-1.5 py-0.5 text-[10px]">
          توصية
        </Badge>
        <span className="mt-0.5 h-1 w-full overflow-hidden rounded-full bg-muted">
          <span className="block h-full rounded-full bg-primary" style={{ width: `${score}%` }} />
        </span>
      </button>
      {breakdown ? (
        <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchorRef}>
          <div className="w-72 space-y-3 p-1" dir="rtl">
            <div>
              <p className="text-sm font-semibold">تفسير نتيجة التوصية</p>
              <p className="mt-1 text-xs text-muted-foreground">
                النتيجة مستقلة عن نتيجة الكتالوج القديمة، والأوزان ثابتة وقابلة للتفسير.
              </p>
            </div>
            {breakdown.factors.map((factor) => (
              <div key={factor.key} className="rounded-md bg-muted/50 p-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{LABELS[factor.key]}</span>
                  <span>{Math.round(factor.weight * 100)}%</span>
                </div>
                <div className="mt-1 flex justify-between text-muted-foreground" dir="ltr">
                  <span>{factor.missing ? "missing" : factor.raw_value ?? "—"}</span>
                  <span>+{factor.contribution.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        </Popover>
      ) : null}
    </>
  );
}

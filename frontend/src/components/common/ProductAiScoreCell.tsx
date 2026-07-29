"use client";

import { useRef, useState } from "react";
import { Badge, Popover } from "@/components/ui/primitives";
import {
  getProductScoreBreakdown,
  getProductScoreQuality,
  type ProductScoreInput,
} from "@/lib/product-score";
import { ProductScoreBreakdown } from "./ProductScoreBreakdown";

export function ProductAiScoreCell({ product }: { product: ProductScoreInput }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const quality = getProductScoreQuality(product.score);
  const breakdown = getProductScoreBreakdown(product);
  const meterWidth = Math.min(100, Math.max(0, product.score));

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
        aria-label={`نتيجة AI ${Math.round(product.score)} — ${quality.label}`}
      >
        <span className="text-base font-semibold leading-none tabular-nums">
          {Math.round(product.score)}
        </span>
        <Badge tone={quality.tone} className="px-1.5 py-0.5 text-[10px]">
          {quality.label}
        </Badge>
        <span className="mt-0.5 h-1 w-full overflow-hidden rounded-full bg-muted">
          <span
            className="block h-full rounded-full bg-primary"
            style={{ width: `${meterWidth}%` }}
          />
        </span>
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchorRef}>
        <ProductScoreBreakdown breakdown={breakdown} compact />
      </Popover>
    </>
  );
}

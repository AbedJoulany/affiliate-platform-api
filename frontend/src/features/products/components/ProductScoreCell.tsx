"use client";

import { Badge } from "@/components/ui/primitives";
import { getScoreQuality } from "../lib/inventory";

export function ProductScoreCell({ score }: { score: number }) {
  const quality = getScoreQuality(score);
  return (
    <div className="space-y-1">
      <span className="block text-base font-semibold tabular-nums">
        {Math.round(score)}
      </span>
      <Badge tone={quality.tone} className="px-1.5 py-0.5 text-[10px]">
        {quality.label}
      </Badge>
    </div>
  );
}

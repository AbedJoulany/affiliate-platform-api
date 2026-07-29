"use client";

import { ProductScoreBreakdown } from "@/components/common/ProductScoreBreakdown";
import type { ScoreBreakdown } from "../types/api";

export function DiscoveryScoreBreakdown({
  breakdown,
  compact = false,
}: {
  breakdown: ScoreBreakdown;
  compact?: boolean;
}) {
  return <ProductScoreBreakdown breakdown={breakdown} compact={compact} />;
}

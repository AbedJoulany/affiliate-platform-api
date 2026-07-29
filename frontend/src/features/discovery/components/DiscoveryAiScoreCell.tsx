"use client";

import { ProductAiScoreCell } from "@/components/common/ProductAiScoreCell";
import type { DiscoveryProduct } from "../types/api";

export function DiscoveryAiScoreCell({ product }: { product: DiscoveryProduct }) {
  return <ProductAiScoreCell product={product} />;
}

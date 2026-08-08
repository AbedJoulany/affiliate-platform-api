import {
  estimateCommissionValue,
  getProductScoreBreakdown,
  getProductScoreQuality,
  type ProductScoreQuality,
} from "@/lib/product-score";
import type { DiscoveryProduct, ScoreBreakdown } from "../types/api";

export type ScoreQualityBand = ProductScoreQuality;

export const getScoreQuality = getProductScoreQuality;
export { estimateCommissionValue };

export function getScoreBreakdown(product: DiscoveryProduct): ScoreBreakdown {
  return getProductScoreBreakdown(product);
}

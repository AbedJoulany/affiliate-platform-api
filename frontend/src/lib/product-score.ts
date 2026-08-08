export type ProductScoreInput = {
  score: number;
  rating: number;
  sales: number;
  discount: number;
  reviews: number;
  score_breakdown?: ProductScoreBreakdown | null;
};

export type ProductScoreFactor = {
  key: "rating" | "sales" | "discount" | "reviews";
  label: string;
  weightPercent: number;
  inputValue: number;
  inputLabel: string;
};

export type ProductScoreBreakdown = {
  total: number;
  factors: ProductScoreFactor[];
  source: "backend" | "documented_weights";
};

export type ProductScoreQuality = {
  key: "excellent" | "high" | "moderate" | "low";
  label: string;
  tone: "success" | "info" | "warning" | "neutral";
  minScore: number;
};

const QUALITY_BANDS: ProductScoreQuality[] = [
  { key: "excellent", label: "ممتاز", tone: "success", minScore: 85 },
  { key: "high", label: "إمكانية عالية", tone: "info", minScore: 70 },
  { key: "moderate", label: "متوسط", tone: "warning", minScore: 55 },
  { key: "low", label: "يحتاج مراجعة", tone: "neutral", minScore: 0 },
];

export function getProductScoreQuality(score: number): ProductScoreQuality {
  return (
    QUALITY_BANDS.find((band) => score >= band.minScore) ??
    QUALITY_BANDS[QUALITY_BANDS.length - 1]
  );
}

export function getProductScoreBreakdown(
  product: ProductScoreInput,
): ProductScoreBreakdown {
  if (product.score_breakdown) return product.score_breakdown;

  return {
    total: product.score,
    source: "documented_weights",
    factors: [
      {
        key: "rating",
        label: "التقييم",
        weightPercent: 40,
        inputValue: product.rating,
        inputLabel: `${product.rating.toFixed(2)} / 5`,
      },
      {
        key: "sales",
        label: "الطلبات",
        weightPercent: 30,
        inputValue: product.sales,
        inputLabel: product.sales.toLocaleString("ar"),
      },
      {
        key: "discount",
        label: "الخصم",
        weightPercent: 20,
        inputValue: product.discount,
        inputLabel: `${product.discount}%`,
      },
      {
        key: "reviews",
        label: "المراجعين / المعايير الأخرى",
        weightPercent: 10,
        inputValue: product.reviews,
        inputLabel: product.reviews.toLocaleString("ar"),
      },
    ],
  };
}

export function estimateCommissionValue(
  price: number,
  commissionRate: number | null | undefined,
): number | null {
  if (commissionRate == null || !Number.isFinite(commissionRate)) return null;
  return (price * commissionRate) / 100;
}

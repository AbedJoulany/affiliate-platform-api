import type { DiscoveryProduct, DiscoveryResponse } from "../types/api";

/** Wire shape before normalization — FastAPI/JSON may emit decimals as strings. */
export type DiscoveryProductRaw = Omit<
  DiscoveryProduct,
  | "price"
  | "original_price"
  | "discount"
  | "rating"
  | "sales"
  | "reviews"
  | "commission_rate"
  | "score"
> & {
  price: number | string;
  original_price?: number | string | null;
  discount: number | string;
  rating: number | string;
  sales: number | string;
  reviews?: number | string;
  commission_rate?: number | string | null;
  score: number | string;
};

export type DiscoveryResponseRaw = Omit<DiscoveryResponse, "items" | "total" | "skip" | "limit" | "page" | "total_pages" | "persisted_count"> & {
  items: DiscoveryProductRaw[];
  total: number | string;
  skip: number | string;
  limit: number | string;
  page: number | string;
  total_pages: number | string;
  persisted_count?: number | string;
};

function toNumber(value: number | string | null | undefined, fallback = 0): number {
  if (value == null || value === "") return fallback;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toNullableNumber(value: number | string | null | undefined): number | null {
  if (value == null || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function normalizeDiscoveryProduct(raw: DiscoveryProductRaw): DiscoveryProduct {
  return {
    ...raw,
    price: toNumber(raw.price),
    original_price: toNullableNumber(raw.original_price),
    discount: toNumber(raw.discount),
    rating: toNumber(raw.rating),
    sales: toNumber(raw.sales),
    reviews: toNumber(raw.reviews),
    commission_rate: toNullableNumber(raw.commission_rate),
    score: toNumber(raw.score),
  };
}

export function normalizeDiscoveryResponse(raw: DiscoveryResponseRaw): DiscoveryResponse {
  return {
    ...raw,
    items: (raw.items ?? []).map(normalizeDiscoveryProduct),
    total: toNumber(raw.total),
    skip: toNumber(raw.skip),
    limit: toNumber(raw.limit),
    page: toNumber(raw.page, 1),
    total_pages: toNumber(raw.total_pages, 1),
    persisted_count: toNumber(raw.persisted_count),
  };
}

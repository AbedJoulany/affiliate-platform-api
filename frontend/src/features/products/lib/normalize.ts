import type { Product, ProductListResponse } from "../types/api";

type NumericProductField =
  | "price"
  | "original_price"
  | "discount"
  | "rating"
  | "sales"
  | "reviews"
  | "commission_rate"
  | "score";

export type RawProduct = Omit<Product, NumericProductField> & {
  price: number | string;
  original_price: number | string | null;
  discount: number | string;
  rating: number | string;
  sales: number | string;
  reviews: number | string;
  commission_rate: number | string | null;
  score: number | string;
};

export type RawProductListResponse = Omit<
  ProductListResponse,
  "items" | "total" | "skip" | "limit"
> & {
  items: RawProduct[];
  total: number | string;
  skip: number | string;
  limit: number | string;
};

function toNumber(value: number | string | null | undefined, fallback = 0): number {
  if (value == null || value === "") return fallback;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toNullableNumber(
  value: number | string | null | undefined,
): number | null {
  if (value == null || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function normalizeProduct(raw: RawProduct): Product {
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

export function normalizeProductList(
  raw: RawProductListResponse,
): ProductListResponse {
  return {
    ...raw,
    items: raw.items.map(normalizeProduct),
    total: toNumber(raw.total),
    skip: toNumber(raw.skip),
    limit: toNumber(raw.limit),
  };
}

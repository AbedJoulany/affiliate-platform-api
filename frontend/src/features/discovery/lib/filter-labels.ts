import type { DiscoveryParams, ProductSort } from "../types/api";

const SORT_LABELS: Record<ProductSort, string> = {
  orders_desc: "الأكثر مبيعًا",
  rating_desc: "الأعلى تقييمًا",
  discount_desc: "الأعلى خصمًا",
  price_asc: "السعر ↑",
  price_desc: "السعر ↓",
  commission_desc: "الأعلى عمولة",
  newest: "الأحدث",
};

export function formatPriceChip(params: DiscoveryParams): string {
  const min = params.min_price;
  const max = params.max_price;
  if (min == null && max == null) return "الكل";
  if (min != null && max != null) return `$${min} – $${max}`;
  if (min != null) return `من $${min}`;
  return `حتى $${max}`;
}

export function formatRatingChip(params: DiscoveryParams): string {
  return params.min_rating != null ? `${params.min_rating}+` : "الكل";
}

export function formatOrdersChip(params: DiscoveryParams): string {
  return params.min_orders != null ? `${params.min_orders.toLocaleString("en")}+` : "الكل";
}

export function formatCommissionChip(params: DiscoveryParams): string {
  return params.min_commission != null ? `${params.min_commission}%+` : "الكل";
}

export function formatSortChip(params: DiscoveryParams): string {
  return SORT_LABELS[params.sort ?? "orders_desc"];
}

export function formatCategoryChip(
  params: DiscoveryParams,
  categories: ReadonlyArray<{ category_id: number; category_name: string }>,
): string {
  if (params.mode !== "category") return "كل المصادر";
  if (!params.category_id) return "اختر فئة";
  const match = categories.find((item) => String(item.category_id) === params.category_id);
  return match?.category_name ?? params.category_id;
}

export { SORT_LABELS };

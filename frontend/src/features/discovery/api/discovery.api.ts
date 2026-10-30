import { apiClient } from "@/services/api-client";
import { normalizeDiscoveryResponse, type DiscoveryResponseRaw } from "../lib/normalize";
import type {
  DiscoveryParams,
  DiscoveryResponse,
  ProductImageSearchRequest,
  ProductImportBatchResponse,
  ProductImportResponse,
} from "../types/api";

type RecommendationProductRaw = {
  id: string;
  aliexpress_product_id: string | null;
  title: string;
  description: string | null;
  price: number | string;
  original_price: number | string | null;
  discount: number | string;
  rating: number | string;
  sales: number | string;
  reviews: number | string;
  image_url: string;
  gallery_images: string[] | null;
  product_url: string;
  affiliate_url: string | null;
  category: string | null;
  store_name: string | null;
  currency: string;
  commission_rate: number | string | null;
  shipping_info: Record<string, unknown> | null;
  score: number | string;
};

type RecommendationScoreBreakdownRaw = {
  total: number | string;
  factors: Array<{
    key: "rating" | "orders" | "discount" | "price" | "commission";
    raw_value: number | string | null;
    normalized_value: number | string;
    weight: number | string;
    contribution: number | string;
    missing: boolean;
  }>;
};

type RecommendationResponseRaw = {
  items: Array<{
    rank: number;
    product: RecommendationProductRaw;
    recommendation_score: number | string;
    score_breakdown: RecommendationScoreBreakdownRaw;
    lacks_affiliate_url: boolean;
  }>;
  total_candidates: number;
  returned: number;
  top_n: number;
};

const toNumber = (value: number | string | null, fallback = 0): number => {
  if (value == null || value === "") return fallback;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export async function recommendProducts(params: DiscoveryParams): Promise<DiscoveryResponse> {
  const { data } = await apiClient.get<RecommendationResponseRaw>("/products/recommendations", {
    params: {
      keywords: params.keywords,
      min_price: params.min_price,
      max_price: params.max_price,
      min_rating: params.min_rating,
      min_orders: params.min_orders,
      min_discount: params.min_discount,
      min_commission: params.min_commission,
      max_commission: params.max_commission,
      top_n: params.top_n ?? 10,
    },
  });

  return {
    items: data.items.map(({ rank, product, recommendation_score, score_breakdown, lacks_affiliate_url }) => ({
      ...product,
      id: product.id,
      aliexpress_product_id: product.aliexpress_product_id ?? product.id,
      gallery_images: product.gallery_images ?? [],
      price: toNumber(product.price),
      original_price: product.original_price == null ? null : toNumber(product.original_price),
      discount: toNumber(product.discount),
      rating: toNumber(product.rating),
      sales: toNumber(product.sales),
      reviews: toNumber(product.reviews),
      commission_rate: product.commission_rate == null ? null : toNumber(product.commission_rate),
      score: toNumber(product.score),
      recommendation_rank: rank,
      recommendation_score: toNumber(recommendation_score),
      recommendation_breakdown: {
        total: toNumber(score_breakdown.total),
        factors: score_breakdown.factors.map((factor) => ({
          ...factor,
          raw_value: factor.raw_value == null ? null : toNumber(factor.raw_value),
          normalized_value: toNumber(factor.normalized_value),
          weight: toNumber(factor.weight),
          contribution: toNumber(factor.contribution),
        })),
      },
      lacks_affiliate_url,
    })),
    total: data.total_candidates,
    skip: 0,
    limit: data.returned,
    page: 1,
    total_pages: 1,
    mode: "recommended",
    sort: "orders_desc",
    persisted_count: 0,
  };
}

export async function discoverProducts(params: DiscoveryParams): Promise<DiscoveryResponse> {
  const mode = params.mode ?? "general";
  if (mode === "recommended") return recommendProducts(params);
  if (mode === "category" && !params.category_id?.trim()) {
    throw new Error("category_id is required for category discovery");
  }
  const path =
    mode === "category" && params.category_id
      ? `/products/discover/category/${params.category_id}`
      : mode === "general"
        ? "/products/discover"
        : `/products/discover/${mode}`;
  const query: Record<string, string | number | boolean | undefined> = {
    keywords: params.keywords,
    min_rating: params.min_rating,
    min_orders: params.min_orders,
    min_price: params.min_price,
    max_price: params.max_price,
    min_discount: params.min_discount,
    shipping_country: params.shipping_country,
    free_shipping: params.free_shipping || undefined,
    choice_only: params.choice_only || undefined,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  };
  const { data } = await apiClient.get<DiscoveryResponseRaw>(path, { params: query });
  return normalizeDiscoveryResponse(data);
}

export async function searchProductsByImage(
  payload: ProductImageSearchRequest,
): Promise<DiscoveryResponse> {
  const { data } = await apiClient.post<DiscoveryResponseRaw>("/products/search/image", payload);
  return normalizeDiscoveryResponse(data);
}

export async function importProduct(productId: string): Promise<ProductImportResponse> {
  const { data } = await apiClient.post<ProductImportResponse>("/products/import", {
    product_id: productId,
  });
  return data;
}

export async function importProductsBatch(
  productIds: string[],
): Promise<ProductImportBatchResponse> {
  const { data } = await apiClient.post<ProductImportBatchResponse>("/products/import/batch", {
    product_ids: productIds,
  });
  return data;
}

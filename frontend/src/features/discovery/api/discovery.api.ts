import { apiClient } from "@/services/api-client";
import type {
  DiscoveryParams,
  DiscoveryResponse,
  ProductImportBatchResponse,
  ProductImportResponse,
} from "../types/api";

export async function discoverProducts(params: DiscoveryParams): Promise<DiscoveryResponse> {
  const mode = params.mode ?? "general";
  if (mode === "category" && !params.category_id?.trim()) {
    throw new Error("category_id is required for category discovery");
  }
  const path =
    mode === "category" && params.category_id
      ? `/products/discover/category/${params.category_id}`
      : mode === "general"
        ? "/products/discover"
        : `/products/discover/${mode}`;
  const query: Record<string, string | number | undefined> = {
    keywords: params.keywords,
    min_rating: params.min_rating,
    min_orders: params.min_orders,
    min_price: params.min_price,
    max_price: params.max_price,
    min_discount: params.min_discount,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  };
  const { data } = await apiClient.get<DiscoveryResponse>(path, { params: query });
  return data;
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

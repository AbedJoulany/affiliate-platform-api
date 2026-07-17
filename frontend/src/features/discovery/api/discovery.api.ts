import { apiClient } from "@/services/api-client";
import type { DiscoveryParams, DiscoveryResponse, ProductImportResponse } from "../types/api";

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
  const query = { ...params };
  delete query.mode;
  delete query.category_id;
  const { data } = await apiClient.get<DiscoveryResponse>(path, { params: query });
  return data;
}

export async function importProduct(productId: string): Promise<ProductImportResponse> {
  const { data } = await apiClient.post<ProductImportResponse>("/products/import", {
    product_id: productId,
  });
  return data;
}

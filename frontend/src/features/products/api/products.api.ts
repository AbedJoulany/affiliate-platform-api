import { apiClient } from "@/services/api-client";
import type { Product, ProductListParams, ProductListResponse } from "../types/api";

export async function getProducts(params: ProductListParams = {}): Promise<ProductListResponse> {
  const { data } = await apiClient.get<ProductListResponse>("/products", { params });
  return data;
}

export async function getProduct(id: string): Promise<Product> {
  const { data } = await apiClient.get<Product>(`/products/${id}`);
  return data;
}

import { apiClient } from "@/services/api-client";
import {
  normalizeProduct,
  normalizeProductList,
  type RawProduct,
  type RawProductListResponse,
} from "../lib/normalize";
import type {
  Product,
  ProductListParams,
  ProductListResponse,
  ProductUpdate,
} from "../types/api";

export async function getProducts(params: ProductListParams = {}): Promise<ProductListResponse> {
  const { data } = await apiClient.get<RawProductListResponse>("/products", { params });
  return normalizeProductList(data);
}

export async function getProduct(id: string): Promise<Product> {
  const { data } = await apiClient.get<RawProduct>(`/products/${id}`);
  return normalizeProduct(data);
}

export async function updateProduct(id: string, input: ProductUpdate): Promise<Product> {
  const { data } = await apiClient.patch<RawProduct>(`/products/${id}`, input);
  return normalizeProduct(data);
}

export async function deleteProduct(id: string): Promise<void> {
  await apiClient.delete(`/products/${id}`);
}

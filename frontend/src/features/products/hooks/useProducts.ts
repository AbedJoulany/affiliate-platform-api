"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getProduct, getProducts } from "../api/products.api";
import type { ProductListParams } from "../types/api";

export const productKeys = {
  all: ["products"] as const,
  list: (params: ProductListParams) => ["products", "list", params] as const,
  detail: (id: string) => ["products", "detail", id] as const,
};

export function useProducts(params: ProductListParams) {
  return useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => getProducts(params),
    placeholderData: keepPreviousData,
  });
}

export function useProduct(id: string) {
  return useQuery({ queryKey: productKeys.detail(id), queryFn: () => getProduct(id), enabled: !!id });
}

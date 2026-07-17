"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { discoverProducts, importProduct } from "../api/discovery.api";
import type { DiscoveryParams } from "../types/api";
import { productKeys } from "@/features/products/hooks/useProducts";

export function useDiscovery(params: DiscoveryParams, enabled: boolean) {
  return useQuery({
    queryKey: ["discovery", params],
    queryFn: () => discoverProducts(params),
    enabled,
    retry: false,
  });
}

export function useImportProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importProduct,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: productKeys.all }),
  });
}

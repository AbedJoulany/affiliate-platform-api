"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  discoverProducts,
  importProduct,
  importProductsBatch,
  searchProductsByImage,
} from "../api/discovery.api";
import { loadDiscoverySession, saveDiscoverySession } from "../lib/session";
import type {
  DiscoveryParams,
  DiscoveryResponse,
  DiscoverySessionSnapshot,
  DiscoveryProduct,
  DiscoveryUiPrefs,
  ProductImageSearchKey,
  ProductImageSearchRequest,
} from "../types/api";
import { productKeys } from "@/features/products/hooks/useProducts";
import type { ApiError } from "@/services/api-client";
import { normalizeUiPrefs } from "../lib/ui-prefs";

export function useDiscoverySession() {
  const [session, setSession] = useState<DiscoverySessionSnapshot>(() => loadDiscoverySession());
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setSession(loadDiscoverySession());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveDiscoverySession(session);
  }, [session, hydrated]);

  const updateDraft = useCallback((patch: Partial<DiscoveryParams>) => {
    setSession((prev) => ({
      ...prev,
      draftParams: { ...prev.draftParams, ...patch },
    }));
  }, []);

  const updateUiPrefs = useCallback((patch: Partial<DiscoveryUiPrefs>) => {
    setSession((prev) => ({
      ...prev,
      uiPrefs: normalizeUiPrefs({ ...normalizeUiPrefs(prev.uiPrefs), ...patch }),
    }));
  }, []);

  const resetDraftFilters = useCallback(() => {
    setSession((prev) => ({
      ...prev,
      draftParams: {
        mode: prev.draftParams.mode ?? "hot",
        sort: "orders_desc",
        page: 1,
        page_size: prev.draftParams.page_size ?? 20,
        category_id: prev.draftParams.mode === "category" ? prev.draftParams.category_id : undefined,
      },
    }));
  }, []);

  const markRunning = useCallback((params: DiscoveryParams) => {
    setSession((prev) => ({
      ...prev,
      committedParams: params,
      draftParams: params,
      lastRunStatus: "running",
      lastError: null,
    }));
  }, []);

  const markSuccess = useCallback((params: DiscoveryParams, response: DiscoveryResponse) => {
    setSession((prev) => ({
      ...prev,
      committedParams: params,
      draftParams: params,
      lastResponse: response,
      lastRunAt: new Date().toISOString(),
      lastRunStatus: "success",
      lastError: null,
    }));
  }, []);

  const markError = useCallback((message: string) => {
    setSession((prev) => ({
      ...prev,
      lastRunStatus: "error",
      lastError: message,
      lastRunAt: new Date().toISOString(),
    }));
  }, []);

  const trackImported = useCallback((ids: string[]) => {
    setSession((prev) => ({
      ...prev,
      importedIds: Array.from(new Set([...prev.importedIds, ...ids])),
    }));
  }, []);

  return {
    session,
    hydrated,
    updateDraft,
    updateUiPrefs,
    resetDraftFilters,
    markRunning,
    markSuccess,
    markError,
    trackImported,
  };
}

export function useDiscoveryQuery(params: DiscoveryParams | null, enabled: boolean) {
  return useQuery({
    queryKey: ["discovery", params],
    queryFn: () => discoverProducts(params as DiscoveryParams),
    enabled: enabled && params != null,
    retry: false,
  });
}

export const imageSearchKeys = {
  all: ["product-image-search"] as const,
  search: (input: ProductImageSearchKey) => ["product-image-search", input] as const,
};

const imageSearchBodies = new Map<string, string>();

export function rememberImageSearchBody(fingerprint: string, imageBase64: string): void {
  imageSearchBodies.set(fingerprint, imageBase64);
}

export function imageSearchFingerprint(file: File): string {
  return `upload:${file.name}:${file.size}:${file.lastModified}`;
}

export function toImageSearchRequest(input: ProductImageSearchKey): ProductImageSearchRequest {
  const page = input.page || 1;
  if (input.source === "url") {
    return { image_url: input.image_url, page, page_size: 20 };
  }
  const image_base64 = input.fingerprint ? imageSearchBodies.get(input.fingerprint) : undefined;
  return { image_base64, page, page_size: 20 };
}

export function useImageSearchQuery(input: ProductImageSearchKey | null, enabled: boolean) {
  const canRun =
    input != null &&
    (input.source === "url"
      ? Boolean(input.image_url)
      : Boolean(input.fingerprint && imageSearchBodies.get(input.fingerprint)));
  return useQuery({
    queryKey: input ? imageSearchKeys.search(input) : imageSearchKeys.all,
    queryFn: () => searchProductsByImage(toImageSearchRequest(input as ProductImageSearchKey)),
    enabled: enabled && canRun,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useImportProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importProduct,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: productKeys.all }),
  });
}

export function useImportProductsBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importProductsBatch,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: productKeys.all }),
  });
}

export function useDiscoverySelection(items: DiscoveryProduct[]) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const itemIds = useMemo(
    () => new Set(items.map((item) => item.aliexpress_product_id)),
    [items],
  );

  useEffect(() => {
    setSelectedIds((prev) => prev.filter((id) => itemIds.has(id)));
  }, [itemIds]);

  const selectedProducts = useMemo(
    () => items.filter((item) => selectedIds.includes(item.aliexpress_product_id)),
    [items, selectedIds],
  );

  const allSelected = items.length > 0 && selectedIds.length === items.length;

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id],
    );
  }, []);

  const toggleAll = useCallback(() => {
    setSelectedIds((prev) =>
      prev.length === items.length ? [] : items.map((item) => item.aliexpress_product_id),
    );
  }, [items]);

  const clear = useCallback(() => setSelectedIds([]), []);

  return { selectedIds, selectedProducts, allSelected, toggle, toggleAll, clear };
}

export type DiscoveryActionError = ApiError | Error;

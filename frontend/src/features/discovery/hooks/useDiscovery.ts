"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { discoverProducts, importProduct, importProductsBatch } from "../api/discovery.api";
import { loadDiscoverySession, saveDiscoverySession } from "../lib/session";
import type {
  DiscoveryParams,
  DiscoveryResponse,
  DiscoverySessionSnapshot,
  DiscoveryProduct,
} from "../types/api";
import { productKeys } from "@/features/products/hooks/useProducts";
import type { ApiError } from "@/services/api-client";

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

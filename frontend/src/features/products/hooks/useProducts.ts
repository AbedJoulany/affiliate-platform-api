"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteProduct, getProduct, getProducts, updateProduct } from "../api/products.api";
import type {
  Product,
  ProductListParams,
  ProductSort,
  ProductStatus,
  ProductTableColumn,
  ProductTableDensity,
} from "../types/api";

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

export function useUpdateProduct() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProductStatus }) =>
      updateProduct(id, { status }),
    onSuccess: (product) => {
      client.setQueryData(productKeys.detail(product.id), product);
      void client.invalidateQueries({ queryKey: productKeys.all });
    },
  });
}

export function useDeleteProduct() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteProduct,
    onSuccess: () => void client.invalidateQueries({ queryKey: productKeys.all }),
  });
}

export const DEFAULT_PRODUCT_COLUMNS: ProductTableColumn[] = [
  "product",
  "price",
  "rating",
  "sales",
  "score",
  "status",
  "actions",
];

export function useProductInventoryState(items: Product[]) {
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [tableDensity, setTableDensity] = useState<ProductTableDensity>("comfortable");
  const [visibleColumns, setVisibleColumns] =
    useState<ProductTableColumn[]>(DEFAULT_PRODUCT_COLUMNS);
  const [sort, setSort] = useState<ProductSort>("newest");
  const [clientSearch, setClientSearch] = useState("");

  const availableIds = useMemo(() => new Set(items.map((item) => item.id)), [items]);

  useEffect(() => {
    setSelectedProductIds((previous) => previous.filter((id) => availableIds.has(id)));
  }, [availableIds]);

  const filteredItems = useMemo(() => {
    const query = clientSearch.trim().toLocaleLowerCase();
    const filtered = query
      ? items.filter((product) =>
          [
            product.title,
            product.category,
            product.store_name,
            product.aliexpress_product_id,
            product.id,
          ]
            .filter(Boolean)
            .some((value) => String(value).toLocaleLowerCase().includes(query)),
        )
      : items;

    return [...filtered].sort((left, right) => {
      switch (sort) {
        case "score_desc":
          return right.score - left.score;
        case "sales_desc":
          return right.sales - left.sales;
        case "rating_desc":
          return right.rating - left.rating;
        case "price_asc":
          return left.price - right.price;
        case "price_desc":
          return right.price - left.price;
        case "newest":
        default:
          return Date.parse(right.created_at) - Date.parse(left.created_at);
      }
    });
  }, [items, clientSearch, sort]);

  const selectedProducts = useMemo(
    () => items.filter((item) => selectedProductIds.includes(item.id)),
    [items, selectedProductIds],
  );

  const toggle = useCallback((id: string) => {
    setSelectedProductIds((previous) =>
      previous.includes(id)
        ? previous.filter((value) => value !== id)
        : [...previous, id],
    );
  }, []);

  const toggleAll = useCallback(() => {
    const visibleIds = filteredItems.map((item) => item.id);
    const allVisibleSelected =
      visibleIds.length > 0 && visibleIds.every((id) => selectedProductIds.includes(id));
    setSelectedProductIds((previous) =>
      allVisibleSelected
        ? previous.filter((id) => !visibleIds.includes(id))
        : Array.from(new Set([...previous, ...visibleIds])),
    );
  }, [filteredItems, selectedProductIds]);

  const toggleColumn = useCallback((column: ProductTableColumn) => {
    if (column === "product" || column === "actions") return;
    setVisibleColumns((previous) =>
      previous.includes(column)
        ? previous.filter((item) => item !== column)
        : [...previous, column],
    );
  }, []);

  return {
    selectedProductIds,
    selectedProducts,
    filteredItems,
    allVisibleSelected:
      filteredItems.length > 0 &&
      filteredItems.every((item) => selectedProductIds.includes(item.id)),
    tableDensity,
    visibleColumns,
    sort,
    clientSearch,
    setTableDensity,
    setSort,
    setClientSearch,
    setSelectedProductIds,
    toggle,
    toggleAll,
    toggleColumn,
    clearSelection: () => setSelectedProductIds([]),
  };
}

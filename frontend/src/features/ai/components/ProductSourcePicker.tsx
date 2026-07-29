"use client";

import { useMemo, useState } from "react";
import { Input, Select } from "@/components/ui/primitives";
import { useProducts } from "@/features/products/hooks/useProducts";
import type { ProductContextState } from "../types/session";

export function ProductSourcePicker({
  value,
  onChange,
}: {
  value: ProductContextState;
  onChange: (patch: Partial<ProductContextState>) => void;
}) {
  const [query, setQuery] = useState("");
  const products = useProducts({ title: query || undefined, limit: 20, skip: 0 });
  const items = products.data?.items ?? [];

  const options = useMemo(
    () =>
      items.map((product) => ({
        id: product.id,
        label: product.title,
      })),
    [items],
  );

  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1.5 block text-sm" htmlFor="ai-source-type">
          اختيار المنتج
        </label>
        <Select
          id="ai-source-type"
          value={value.sourceType}
          onChange={(event) =>
            onChange({
              sourceType: event.target.value as "product" | "url",
              productId: event.target.value === "product" ? value.productId : null,
              url: event.target.value === "url" ? value.url : null,
            })
          }
        >
          <option value="product">منتج مستورد</option>
          <option value="url">رابط AliExpress</option>
        </Select>
      </div>

      {value.sourceType === "product" ? (
        <div className="space-y-2">
          <Input
            placeholder="ابحث عن منتج…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="بحث المنتجات"
          />
          <Select
            value={value.productId ?? ""}
            onChange={(event) => {
              const id = event.target.value || null;
              const match = options.find((item) => item.id === id);
              onChange({
                productId: id,
                productLabel: match?.label ?? null,
                url: null,
              });
            }}
            aria-label="اختيار المنتج"
          >
            <option value="">اختر منتجًا</option>
            {options.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </Select>
          {products.isPending ? (
            <p className="text-xs text-muted-foreground">جارٍ تحميل المنتجات…</p>
          ) : null}
        </div>
      ) : (
        <div>
          <label className="mb-1.5 block text-sm" htmlFor="ai-product-url">
            رابط المنتج
          </label>
          <Input
            id="ai-product-url"
            dir="ltr"
            placeholder="https://www.aliexpress.com/item/..."
            value={value.url ?? ""}
            onChange={(event) =>
              onChange({
                url: event.target.value,
                productId: null,
                productLabel: null,
              })
            }
          />
        </div>
      )}
    </div>
  );
}

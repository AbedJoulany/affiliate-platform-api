"use client";

import type { ReactNode } from "react";
import { Input, Select } from "@/components/ui/primitives";
import type { DiscoveryMode, DiscoveryParams, ProductSort } from "../types/api";

const SORT_OPTIONS: ReadonlyArray<{ value: ProductSort; label: string }> = [
  { value: "orders_desc", label: "الأكثر مبيعًا" },
  { value: "rating_desc", label: "الأعلى تقييمًا" },
  { value: "discount_desc", label: "الأعلى خصمًا" },
  { value: "price_asc", label: "السعر تصاعديًا" },
  { value: "price_desc", label: "السعر تنازليًا" },
  { value: "commission_desc", label: "الأعلى عمولة" },
  { value: "newest", label: "الأحدث" },
];

export function DiscoveryFilterPanel({
  params,
  categories,
  categoriesLoading,
  categoryError,
  onChange,
}: {
  params: DiscoveryParams;
  categories: ReadonlyArray<{ category_id: number; category_name: string }>;
  categoriesLoading: boolean;
  categoryError?: string;
  onChange: (patch: Partial<DiscoveryParams>) => void;
}) {
  const mode = params.mode ?? "hot";

  return (
    <aside className="space-y-4 rounded-lg border border-border bg-surface p-4" aria-label="فلاتر الاكتشاف">
      <div>
        <h2 className="text-sm font-semibold">تحسين النتائج</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          الفلاتر تُطبَّق عند تشغيل الاكتشاف. الملفات المحفوظة والجدولة امتداد مستقبلي.
        </p>
      </div>

      {(mode === "general" || mode === "hot" || mode === "trending") && (
        <Field label="كلمات البحث" htmlFor="discovery-keywords">
          <Input
            id="discovery-keywords"
            value={params.keywords ?? ""}
            onChange={(event) => onChange({ keywords: event.target.value || undefined })}
          />
        </Field>
      )}

      {mode === "category" && (
        <Field label="الفئة" htmlFor="discovery-category">
          <Select
            id="discovery-category"
            disabled={categoriesLoading}
            value={params.category_id ?? ""}
            aria-invalid={Boolean(categoryError)}
            onChange={(event) => onChange({ category_id: event.target.value || undefined })}
          >
            <option value="">اختر فئة</option>
            {categories.map((category) => (
              <option key={category.category_id} value={String(category.category_id)}>
                {category.category_name}
              </option>
            ))}
          </Select>
          {categoryError && <p className="mt-1 text-sm text-destructive">{categoryError}</p>}
        </Field>
      )}

      <Field label="الترتيب" htmlFor="discovery-sort">
        <Select
          id="discovery-sort"
          value={params.sort ?? "orders_desc"}
          onChange={(event) => onChange({ sort: event.target.value as ProductSort })}
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </Field>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="أدنى تقييم" htmlFor="discovery-rating">
          <Input
            id="discovery-rating"
            type="number"
            step="0.1"
            min={0}
            max={5}
            value={params.min_rating ?? ""}
            onChange={(event) =>
              onChange({
                min_rating: event.target.value === "" ? undefined : Number(event.target.value),
              })
            }
          />
        </Field>
        <Field label="أدنى طلبات" htmlFor="discovery-orders">
          <Input
            id="discovery-orders"
            type="number"
            min={0}
            value={params.min_orders ?? ""}
            onChange={(event) =>
              onChange({
                min_orders: event.target.value === "" ? undefined : Number(event.target.value),
              })
            }
          />
        </Field>
        <Field label="أدنى سعر" htmlFor="discovery-min-price">
          <Input
            id="discovery-min-price"
            type="number"
            min={0}
            value={params.min_price ?? ""}
            onChange={(event) =>
              onChange({
                min_price: event.target.value === "" ? undefined : Number(event.target.value),
              })
            }
          />
        </Field>
        <Field label="أقصى سعر" htmlFor="discovery-max-price">
          <Input
            id="discovery-max-price"
            type="number"
            min={0}
            value={params.max_price ?? ""}
            onChange={(event) =>
              onChange({
                max_price: event.target.value === "" ? undefined : Number(event.target.value),
              })
            }
          />
        </Field>
        <Field label="أدنى خصم %" htmlFor="discovery-discount">
          <Input
            id="discovery-discount"
            type="number"
            min={0}
            max={100}
            value={params.min_discount ?? ""}
            onChange={(event) =>
              onChange({
                min_discount: event.target.value === "" ? undefined : Number(event.target.value),
              })
            }
          />
        </Field>
        <Field label="حجم الصفحة" htmlFor="discovery-page-size">
          <Select
            id="discovery-page-size"
            value={String(params.page_size ?? 20)}
            onChange={(event) => onChange({ page_size: Number(event.target.value), page: 1 })}
          >
            {[10, 20, 30, 50].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {/* Extension: saved filters, scoring profiles, free_shipping, choice_only */}
    </aside>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  );
}

export function validateDiscoveryDraft(params: DiscoveryParams): string | null {
  const mode = params.mode ?? "hot";
  if (mode === "category" && !params.category_id?.trim()) return "اختر فئة قبل التشغيل.";
  return null;
}

export type { DiscoveryMode };

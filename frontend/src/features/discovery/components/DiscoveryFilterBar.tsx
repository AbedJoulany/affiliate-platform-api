"use client";

import { SlidersHorizontal } from "lucide-react";
import { Button, Input, Select } from "@/components/ui/primitives";
import {
  formatCategoryChip,
  formatCommissionChip,
  formatOrdersChip,
  formatPriceChip,
  formatRatingChip,
  formatSortChip,
  SORT_LABELS,
} from "../lib/filter-labels";
import type { DiscoveryParams, ProductSort } from "../types/api";
import { DiscoveryFilterChip } from "./DiscoveryFilterChip";

const PRICE_PRESETS = [
  { label: "الكل", min: undefined, max: undefined },
  { label: "$0 – $25", min: 0, max: 25 },
  { label: "$0 – $50", min: 0, max: 50 },
  { label: "$0 – $100", min: 0, max: 100 },
  { label: "$0 – $500", min: 0, max: 500 },
] as const;

const RATING_PRESETS = [undefined, 4, 4.5, 4.7] as const;
const ORDERS_PRESETS = [undefined, 1000, 5000, 10000] as const;
const COMMISSION_PRESETS = [undefined, 5, 8, 12] as const;

export function DiscoveryFilterBar({
  params,
  categories,
  totalProducts,
  onChange,
  onOpenAdvanced,
}: {
  params: DiscoveryParams;
  categories: ReadonlyArray<{ category_id: number; category_name: string }>;
  totalProducts: number | null;
  onChange: (patch: Partial<DiscoveryParams>) => void;
  onOpenAdvanced: () => void;
}) {
  return (
    <div
      className="flex flex-wrap items-end gap-2 rounded-lg border border-border bg-muted/50 p-2"
      aria-label="شريط فلاتر الاكتشاف"
    >
      <Button
        type="button"
        variant="outline"
        className="h-auto min-h-10 gap-2 px-3 py-2"
        onClick={onOpenAdvanced}
      >
        <SlidersHorizontal className="size-4" aria-hidden />
        فلاتر متقدمة
      </Button>

      <DiscoveryFilterChip label="الفئة" value={formatCategoryChip(params, categories)}>
        <Select
          value={params.mode === "category" ? (params.category_id ?? "") : ""}
          onChange={(event) => {
            const value = event.target.value;
            if (!value) {
              onChange({ mode: "hot", category_id: undefined, page: 1 });
              return;
            }
            onChange({ mode: "category", category_id: value, page: 1 });
          }}
        >
          <option value="">كل المصادر</option>
          {categories.map((category) => (
            <option key={category.category_id} value={String(category.category_id)}>
              {category.category_name}
            </option>
          ))}
        </Select>
      </DiscoveryFilterChip>

      <DiscoveryFilterChip label="السعر" value={formatPriceChip(params)}>
        <div className="flex flex-col gap-2">
          {PRICE_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className="rounded-md px-2 py-1.5 text-start text-sm hover:bg-muted"
              onClick={() => onChange({ min_price: preset.min, max_price: preset.max, page: 1 })}
            >
              {preset.label}
            </button>
          ))}
          <div className="grid grid-cols-2 gap-2">
            <Input
              type="number"
              min={0}
              placeholder="أدنى"
              value={params.min_price ?? ""}
              onChange={(event) =>
                onChange({
                  min_price: event.target.value === "" ? undefined : Number(event.target.value),
                  page: 1,
                })
              }
            />
            <Input
              type="number"
              min={0}
              placeholder="أقصى"
              value={params.max_price ?? ""}
              onChange={(event) =>
                onChange({
                  max_price: event.target.value === "" ? undefined : Number(event.target.value),
                  page: 1,
                })
              }
            />
          </div>
        </div>
      </DiscoveryFilterChip>

      <DiscoveryFilterChip label="التقييم" value={formatRatingChip(params)}>
        <div className="flex flex-col gap-1">
          {RATING_PRESETS.map((value) => (
            <button
              key={String(value)}
              type="button"
              className="rounded-md px-2 py-1.5 text-start text-sm hover:bg-muted"
              onClick={() => onChange({ min_rating: value, page: 1 })}
            >
              {value == null ? "الكل" : `${value}+`}
            </button>
          ))}
        </div>
      </DiscoveryFilterChip>

      <DiscoveryFilterChip label="الطلبات" value={formatOrdersChip(params)}>
        <div className="flex flex-col gap-1">
          {ORDERS_PRESETS.map((value) => (
            <button
              key={String(value)}
              type="button"
              className="rounded-md px-2 py-1.5 text-start text-sm hover:bg-muted"
              onClick={() => onChange({ min_orders: value, page: 1 })}
            >
              {value == null ? "الكل" : `${value.toLocaleString("en")}+`}
            </button>
          ))}
        </div>
      </DiscoveryFilterChip>

      <DiscoveryFilterChip label="العمولة" value={formatCommissionChip(params)}>
        <p className="text-xs text-muted-foreground">عرض فقط — سيتم دعمه في الـ API لاحقًا</p>
        <div className="mt-2 flex flex-col gap-1">
          {COMMISSION_PRESETS.map((value) => (
            <button
              key={String(value)}
              type="button"
              className="rounded-md px-2 py-1.5 text-start text-sm hover:bg-muted"
              onClick={() => onChange({ min_commission: value, page: 1 })}
            >
              {value == null ? "الكل" : `${value}%+`}
            </button>
          ))}
        </div>
      </DiscoveryFilterChip>

      <DiscoveryFilterChip label="الترتيب" value={formatSortChip(params)}>
        <Select
          value={params.sort ?? "orders_desc"}
          onChange={(event) => onChange({ sort: event.target.value as ProductSort, page: 1 })}
        >
          {(Object.entries(SORT_LABELS) as Array<[ProductSort, string]>).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </DiscoveryFilterChip>

      <div className="ms-auto px-2 py-1.5 text-sm font-semibold tabular-nums">
        {totalProducts == null ? "—" : `${totalProducts.toLocaleString("ar")} منتج`}
      </div>
    </div>
  );
}

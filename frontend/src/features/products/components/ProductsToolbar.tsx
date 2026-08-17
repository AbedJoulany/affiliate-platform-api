"use client";

import { Columns3 } from "lucide-react";
import { WorkspaceResultsToolbar } from "@/components/common/WorkspaceResultsToolbar";
import { Select } from "@/components/ui/primitives";
import type {
  ProductSort,
  ProductStatus,
  ProductTableColumn,
  ProductTableDensity,
} from "../types/api";
import { productStatusOptions } from "../lib/schemas";

const COLUMN_LABELS: Record<ProductTableColumn, string> = {
  product: "المنتج",
  price: "السعر",
  rating: "التقييم",
  sales: "المبيعات",
  score: "نتيجة AI",
  status: "الحالة",
  actions: "الإجراءات",
};

export function ProductsToolbar({
  search,
  status,
  sort,
  density,
  visibleColumns,
  pageSize,
  productCount,
  refreshing,
  onSearchChange,
  onStatusChange,
  onSortChange,
  onDensityChange,
  onToggleColumn,
  onPageSizeChange,
  onRefresh,
}: {
  search: string;
  status: ProductStatus | "";
  sort: ProductSort;
  density: ProductTableDensity;
  visibleColumns: ProductTableColumn[];
  pageSize: number;
  productCount: number;
  refreshing: boolean;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: ProductStatus | "") => void;
  onSortChange: (value: ProductSort) => void;
  onDensityChange: (value: ProductTableDensity) => void;
  onToggleColumn: (column: ProductTableColumn) => void;
  onPageSizeChange: (value: number) => void;
  onRefresh: () => void;
}) {
  const filters = (
    <Select
      className="w-auto"
      aria-label="تصفية حسب الحالة"
      value={status}
      onChange={(event) => onStatusChange(event.target.value as ProductStatus | "")}
    >
      <option value="">كل الحالات</option>
      {productStatusOptions.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </Select>
  );

  const columns = (
    <details className="relative">
      <summary className="flex h-10 cursor-pointer list-none items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm hover:bg-muted">
        <Columns3 className="size-4" />
        الأعمدة
      </summary>
      <div className="absolute end-0 z-30 mt-1 w-44 rounded-md border border-border bg-surface p-2 shadow-lg">
        {(Object.keys(COLUMN_LABELS) as ProductTableColumn[]).map((column) => (
          <label
            key={column}
            className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted"
          >
            <input
              type="checkbox"
              checked={visibleColumns.includes(column)}
              disabled={column === "product" || column === "actions"}
              onChange={() => onToggleColumn(column)}
            />
            {COLUMN_LABELS[column]}
          </label>
        ))}
      </div>
    </details>
  );

  return (
    <WorkspaceResultsToolbar
      search={search}
      onSearchChange={onSearchChange}
      searchLabel="البحث في مخزون المنتجات"
      searchPlaceholder="العنوان، الفئة، المتجر أو SKU…"
      countLabel={`${productCount.toLocaleString("ar")} منتج`}
      filters={filters}
      sort={{
        value: sort,
        label: "ترتيب المنتجات",
        options: [
          { value: "newest", label: "الأحدث" },
          { value: "score_desc", label: "أعلى نتيجة AI" },
          { value: "sales_desc", label: "الأكثر مبيعًا" },
          { value: "rating_desc", label: "الأعلى تقييمًا" },
          { value: "price_asc", label: "السعر تصاعديًا" },
          { value: "price_desc", label: "السعر تنازليًا" },
        ],
        onChange: onSortChange,
      }}
      density={{
        value: density,
        label: "كثافة الجدول",
        options: [
          { value: "comfortable", label: "مريح" },
          { value: "compact", label: "مضغوط" },
        ],
        onChange: onDensityChange,
      }}
      columns={columns}
      pageSize={{ value: pageSize, options: [10, 25, 50, 100], onChange: onPageSizeChange }}
      refreshing={refreshing}
      onRefresh={onRefresh}
    />
  );
}

"use client";

import { Columns3, RefreshCw, Search } from "lucide-react";
import { Button, Input, Select } from "@/components/ui/primitives";
import type {
  DiscoveryResponse,
  DiscoveryTableColumn,
  TableDensity,
} from "../types/api";

const COLUMN_LABELS: Record<DiscoveryTableColumn, string> = {
  product: "المنتج",
  price: "السعر",
  rating: "التقييم",
  orders: "الطلبات",
  commission: "العمولة",
  score: "نتيجة AI",
  status: "الحالة",
  actions: "إجراءات",
};

export function DiscoveryResultsToolbar({
  response,
  search,
  density,
  visibleColumns,
  refreshing,
  onSearchChange,
  onDensityChange,
  onToggleColumn,
  onRefresh,
  onPageChange,
}: {
  response: DiscoveryResponse | null;
  search: string;
  density: TableDensity;
  visibleColumns: DiscoveryTableColumn[];
  refreshing: boolean;
  onSearchChange: (value: string) => void;
  onDensityChange: (value: TableDensity) => void;
  onToggleColumn: (column: DiscoveryTableColumn) => void;
  onRefresh: () => void;
  onPageChange: (page: number) => void;
}) {
  const page = response?.page ?? 1;
  const totalPages = Math.max(response?.total_pages ?? 1, 1);
  const total = response?.total ?? 0;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative min-w-[12rem] flex-1">
        <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="ps-9"
          placeholder="بحث في نتائج الصفحة…"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          aria-label="بحث في النتائج"
        />
      </div>

      <p className="text-sm text-muted-foreground tabular-nums">
        {total.toLocaleString("ar")} نتيجة
        {response ? ` · ص ${page.toLocaleString("ar")}/${totalPages.toLocaleString("ar")}` : ""}
      </p>

      <Select
        className="w-auto"
        value={density}
        onChange={(event) => onDensityChange(event.target.value as TableDensity)}
        aria-label="كثافة الجدول"
      >
        <option value="comfortable">مريح</option>
        <option value="compact">مضغوط</option>
      </Select>

      <details className="relative">
        <summary className="flex h-10 cursor-pointer list-none items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm hover:bg-muted">
          <Columns3 className="size-4" aria-hidden />
          الأعمدة
        </summary>
        <div className="absolute end-0 z-20 mt-1 w-48 rounded-md border border-border bg-surface p-2 shadow-lg">
          {(Object.keys(COLUMN_LABELS) as DiscoveryTableColumn[]).map((column) => (
            <label key={column} className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted">
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

      <Button type="button" variant="outline" loading={refreshing} onClick={onRefresh}>
        <RefreshCw className="size-4" aria-hidden />
        تحديث
      </Button>

      {response ? (
        <div className="flex items-center gap-2">
          <Button variant="outline" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
            السابق
          </Button>
          <Button
            variant="outline"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            التالي
          </Button>
        </div>
      ) : null}
    </div>
  );
}

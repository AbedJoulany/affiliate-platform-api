"use client";

import Image from "next/image";
import { Badge, Button } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/utils";
import type { DiscoveryProduct, DiscoveryResultsView } from "../types/api";

export function DiscoveryResultsTable({
  items,
  selectedIds,
  allSelected,
  importedIds,
  canImport,
  importingId,
  view = "table",
  onToggle,
  onToggleAll,
  onInspect,
  onScoreClick,
  onImport,
}: {
  items: DiscoveryProduct[];
  selectedIds: string[];
  allSelected: boolean;
  importedIds: ReadonlySet<string>;
  canImport: boolean;
  importingId: string | null;
  view?: DiscoveryResultsView;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onInspect: (product: DiscoveryProduct) => void;
  onScoreClick: (product: DiscoveryProduct) => void;
  onImport: (product: DiscoveryProduct) => void;
}) {
  // Default and only implemented view for v1. Grid can plug in later via `view`.
  if (view !== "table") {
    return (
      <p className="rounded-md border border-dashed border-border p-6 text-sm text-muted-foreground">
        عرض الشبكة غير مفعّل بعد. الجدول هو العرض الافتراضي.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[980px] text-sm">
        <thead className="bg-muted/60 text-right text-muted-foreground">
          <tr>
            <th className="p-3" scope="col">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                aria-label="تحديد كل النتائج"
              />
            </th>
            <th className="p-3" scope="col">المنتج</th>
            <th className="p-3" scope="col">السعر</th>
            <th className="p-3" scope="col">نتيجة AI</th>
            <th className="p-3" scope="col">تقييم</th>
            <th className="p-3" scope="col">طلبات</th>
            <th className="p-3" scope="col">خصم</th>
            <th className="p-3" scope="col">عمولة</th>
            <th className="p-3" scope="col">الحالة</th>
            <th className="p-3" scope="col">إجراءات</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((product) => {
            const selected = selectedIds.includes(product.aliexpress_product_id);
            const imported = importedIds.has(product.aliexpress_product_id);
            return (
              <tr key={product.aliexpress_product_id} className="align-middle">
                <td className="p-3">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggle(product.aliexpress_product_id)}
                    aria-label={`تحديد ${product.title}`}
                  />
                </td>
                <td className="p-3">
                  <button
                    type="button"
                    className="flex max-w-sm items-start gap-3 text-right hover:opacity-90"
                    onClick={() => onInspect(product)}
                  >
                    <span className="relative mt-0.5 size-12 shrink-0 overflow-hidden rounded-md bg-muted">
                      <Image src={product.image_url} alt="" fill className="object-cover" sizes="48px" />
                    </span>
                    <span>
                      <span className="line-clamp-2 font-medium">{product.title}</span>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {product.store_name ?? product.category ?? product.aliexpress_product_id}
                      </span>
                    </span>
                  </button>
                </td>
                <td className="p-3 font-medium tabular-nums">
                  {formatMoney(product.price, product.currency)}
                </td>
                <td className="p-3">
                  <button type="button" onClick={() => onScoreClick(product)}>
                    <Badge tone="info">{product.score.toFixed(2)}</Badge>
                  </button>
                </td>
                <td className="p-3 tabular-nums">{product.rating.toFixed(1)}</td>
                <td className="p-3 tabular-nums">{product.sales.toLocaleString("ar")}</td>
                <td className="p-3 tabular-nums">{product.discount}%</td>
                <td className="p-3 tabular-nums">
                  {product.commission_rate != null ? `${product.commission_rate}%` : "—"}
                </td>
                <td className="p-3">
                  <Badge tone={imported ? "success" : "neutral"}>
                    {imported ? "مستورد" : "مرشّح"}
                  </Badge>
                </td>
                <td className="p-3">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" className="px-2" onClick={() => onInspect(product)}>
                      معاينة
                    </Button>
                    <Button
                      variant="outline"
                      disabled={!canImport || imported}
                      loading={importingId === product.aliexpress_product_id}
                      onClick={() => onImport(product)}
                    >
                      استيراد
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

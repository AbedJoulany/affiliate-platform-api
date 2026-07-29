"use client";

import Image from "next/image";
import { Badge, Button } from "@/components/ui/primitives";
import {
  ProductImageHoverPreview,
  useProductImageHover,
} from "@/components/common/ProductImageHoverPreview";
import { formatMoney } from "@/lib/utils";
import { estimateCommissionValue } from "../lib/score-explanation";
import type {
  DiscoveryProduct,
  DiscoveryResultsView,
  DiscoveryTableColumn,
  TableDensity,
} from "../types/api";
import { DiscoveryAiScoreCell } from "./DiscoveryAiScoreCell";

export function DiscoveryResultsTable({
  items,
  selectedIds,
  allSelected,
  importedIds,
  canImport,
  importingId,
  density = "comfortable",
  visibleColumns,
  view = "table",
  onToggle,
  onToggleAll,
  onInspect,
  onImport,
  onGenerateAi,
  onAddToQueue,
}: {
  items: DiscoveryProduct[];
  selectedIds: string[];
  allSelected: boolean;
  importedIds: ReadonlySet<string>;
  canImport: boolean;
  importingId: string | null;
  density?: TableDensity;
  visibleColumns: DiscoveryTableColumn[];
  view?: DiscoveryResultsView;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onInspect: (product: DiscoveryProduct) => void;
  onImport: (product: DiscoveryProduct) => void;
  onGenerateAi: (product: DiscoveryProduct) => void;
  onAddToQueue: (product: DiscoveryProduct) => void;
}) {
  const hover = useProductImageHover();
  const cellPad = density === "compact" ? "px-2 py-1.5" : "p-3";
  const show = (column: DiscoveryTableColumn) => visibleColumns.includes(column);

  if (view !== "table") {
    return (
      <p className="rounded-md border border-dashed border-border p-6 text-sm text-muted-foreground">
        عرض الشبكة غير مفعّل بعد. الجدول هو العرض الافتراضي.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[1100px] table-fixed text-sm">
        <thead className="bg-muted/60 text-right text-muted-foreground">
          <tr>
            <th className={`${cellPad} w-10`} scope="col">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                aria-label="تحديد كل النتائج"
                onClick={(event) => event.stopPropagation()}
              />
            </th>
            {show("product") ? (
              <th className={`${cellPad} w-[28%]`} scope="col">
                المنتج
              </th>
            ) : null}
            {show("price") ? (
              <th className={`${cellPad} w-[12%]`} scope="col">
                السعر
              </th>
            ) : null}
            {show("rating") ? (
              <th className={`${cellPad} w-[8%]`} scope="col">
                التقييم
              </th>
            ) : null}
            {show("orders") ? (
              <th className={`${cellPad} w-[10%]`} scope="col">
                الطلبات
              </th>
            ) : null}
            {show("commission") ? (
              <th className={`${cellPad} w-[12%]`} scope="col">
                العمولة
              </th>
            ) : null}
            {show("score") ? (
              <th className={`${cellPad} w-[12%]`} scope="col">
                نتيجة AI
              </th>
            ) : null}
            {show("status") ? (
              <th className={`${cellPad} w-[8%]`} scope="col">
                الحالة
              </th>
            ) : null}
            {show("actions") ? (
              <th className={`${cellPad} w-[14%]`} scope="col">
                إجراءات
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((product) => {
            const selected = selectedIds.includes(product.aliexpress_product_id);
            const imported = importedIds.has(product.aliexpress_product_id);
            const commissionValue = estimateCommissionValue(
              product.price,
              product.commission_rate,
            );
            return (
              <tr
                key={product.aliexpress_product_id}
                className="align-middle cursor-pointer hover:bg-muted/40"
                onClick={() => onInspect(product)}
              >
                <td className={cellPad} onClick={(event) => event.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggle(product.aliexpress_product_id)}
                    aria-label={`تحديد ${product.title}`}
                  />
                </td>
                {show("product") ? (
                  <td className={cellPad}>
                    <div className="flex min-w-0 items-start gap-3">
                      <span
                        className="relative mt-0.5 size-12 shrink-0 overflow-hidden rounded-md bg-muted"
                        onPointerEnter={(event) =>
                          hover.show(
                            {
                              src: product.image_url,
                              title: product.title,
                              price: product.price,
                              currency: product.currency,
                              discount: product.discount,
                            },
                            event,
                          )
                        }
                        onPointerMove={hover.move}
                        onPointerLeave={hover.hide}
                      >
                        <Image
                          src={product.image_url}
                          alt=""
                          fill
                          className="object-cover"
                          sizes="48px"
                        />
                      </span>
                      <span className="min-w-0">
                        <span className="line-clamp-2 font-semibold">{product.title}</span>
                        <span className="mt-1 block truncate text-xs text-muted-foreground">
                          {[product.category, product.store_name].filter(Boolean).join(" · ") ||
                            product.aliexpress_product_id}
                        </span>
                      </span>
                    </div>
                  </td>
                ) : null}
                {show("price") ? (
                  <td className={`${cellPad} tabular-nums`}>
                    <div className="font-semibold">{formatMoney(product.price, product.currency)}</div>
                    {product.discount > 0 ? (
                      <div className="mt-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                        خصم {product.discount}%
                      </div>
                    ) : (
                      <div className="mt-0.5 text-xs text-muted-foreground">بدون خصم</div>
                    )}
                  </td>
                ) : null}
                {show("rating") ? (
                  <td className={`${cellPad} tabular-nums`}>{product.rating.toFixed(1)}</td>
                ) : null}
                {show("orders") ? (
                  <td className={`${cellPad} tabular-nums`}>
                    {product.sales.toLocaleString("ar")}
                  </td>
                ) : null}
                {show("commission") ? (
                  <td className={`${cellPad} tabular-nums`}>
                    {product.commission_rate != null ? (
                      <>
                        <div className="font-medium">{product.commission_rate}%</div>
                        {commissionValue != null ? (
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            ≈ {formatMoney(commissionValue, product.currency)}
                          </div>
                        ) : null}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                ) : null}
                {show("score") ? (
                  <td className={cellPad} onClick={(event) => event.stopPropagation()}>
                    <DiscoveryAiScoreCell product={product} />
                  </td>
                ) : null}
                {show("status") ? (
                  <td className={cellPad}>
                    <Badge tone={imported ? "success" : "neutral"}>
                      {imported ? "مستورد" : "مرشّح"}
                    </Badge>
                  </td>
                ) : null}
                {show("actions") ? (
                  <td className={cellPad} onClick={(event) => event.stopPropagation()}>
                    <div className="flex flex-wrap gap-1.5">
                      <Button
                        variant="ghost"
                        className="h-8 px-2"
                        onClick={() => onInspect(product)}
                      >
                        معاينة
                      </Button>
                      <Button
                        variant="outline"
                        className="h-8 px-2"
                        disabled={!canImport || imported}
                        loading={importingId === product.aliexpress_product_id}
                        onClick={() => onImport(product)}
                      >
                        استيراد
                      </Button>
                      <Button
                        variant="ghost"
                        className="h-8 px-2"
                        onClick={() => onGenerateAi(product)}
                      >
                        AI
                      </Button>
                      <Button
                        variant="ghost"
                        className="h-8 px-2"
                        onClick={() => onAddToQueue(product)}
                      >
                        قائمة
                      </Button>
                    </div>
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
      <ProductImageHoverPreview payload={hover.payload} />
    </div>
  );
}

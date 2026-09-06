"use client";

import Image from "next/image";
import { Package } from "lucide-react";
import {
  ProductImageHoverPreview,
  useProductImageHover,
} from "@/components/common/ProductImageHoverPreview";
import { ProductAiScoreCell } from "@/components/common/ProductAiScoreCell";
import { Badge } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/utils";
import type { QueueItem } from "@/features/queue/types/api";
import {
  formatCompactNumber,
  getProductPipelineState,
} from "../lib/inventory";
import type {
  Product,
  ProductTableColumn,
  ProductTableDensity,
} from "../types/api";
import { productStatusLabels } from "../lib/schemas";
import { ProductActionsMenu } from "./ProductActionsMenu";
import { ProductHealthBadges } from "./ProductHealthBadges";

export function ProductsTable({
  items,
  selectedProductIds,
  allSelected,
  density,
  visibleColumns,
  queueIndex,
  canManage,
  onToggle,
  onToggleAll,
  onPreview,
  onGenerate,
  onDelete,
}: {
  items: Product[];
  selectedProductIds: string[];
  allSelected: boolean;
  density: ProductTableDensity;
  visibleColumns: ProductTableColumn[];
  queueIndex: ReadonlyMap<string, QueueItem[]>;
  canManage: boolean;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onPreview: (product: Product) => void;
  onGenerate: (product: Product) => void;
  onDelete: (product: Product) => void;
}) {
  const hover = useProductImageHover();
  const cellPadding = density === "compact" ? "px-3 py-2" : "px-4 py-3";
  const imageSize = density === "compact" ? "size-12" : "size-14";
  const show = (column: ProductTableColumn) => visibleColumns.includes(column);

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[1020px] table-fixed text-sm">
        <thead className="bg-muted/60 text-right text-muted-foreground">
          <tr>
            <th className={`${cellPadding} w-12`} scope="col">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                aria-label="تحديد كل المنتجات المعروضة"
              />
            </th>
            {show("product") ? (
              <th className={`${cellPadding} w-[34%]`} scope="col">
                المنتج
              </th>
            ) : null}
            {show("price") ? <th className={`${cellPadding} w-[11%]`}>السعر</th> : null}
            {show("rating") ? <th className={`${cellPadding} w-[9%]`}>التقييم</th> : null}
            {show("sales") ? <th className={`${cellPadding} w-[10%]`}>المبيعات</th> : null}
            {show("score") ? <th className={`${cellPadding} w-[11%]`}>نتيجة AI</th> : null}
            {show("status") ? <th className={`${cellPadding} w-[18%]`}>الحالة</th> : null}
            {show("actions") ? (
              <th className={`${cellPadding} w-[7%] text-center`}>الإجراءات</th>
            ) : null}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((product) => {
            const selected = selectedProductIds.includes(product.id);
            const pipelineState = getProductPipelineState(product, queueIndex);
            return (
              <tr
                key={product.id}
                className="cursor-pointer align-middle outline-none transition hover:bg-muted/35 hover:shadow-[inset_0_1px_0_hsl(var(--border)),inset_0_-1px_0_hsl(var(--border))] focus-visible:bg-muted/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
                tabIndex={0}
                onClick={() => onPreview(product)}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget) return;
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onPreview(product);
                  }
                }}
              >
                <td
                  className={cellPadding}
                  onClick={(event) => event.stopPropagation()}
                  onPointerDown={(event) => event.stopPropagation()}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggle(product.id)}
                    onClick={(event) => event.stopPropagation()}
                    aria-label={`تحديد ${product.title}`}
                  />
                </td>
                {show("product") ? (
                  <td className={cellPadding}>
                    <div className="flex min-w-0 items-center gap-3">
                      <button
                        type="button"
                        className={`relative ${imageSize} shrink-0 overflow-hidden rounded-lg bg-muted`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onPreview(product);
                        }}
                        onPointerEnter={(event) => {
                          if (!product.image_url) return;
                          hover.show(
                            {
                              src: product.image_url,
                              title: product.title,
                              price: product.price,
                              currency: product.currency,
                              discount: product.discount,
                            },
                            event,
                          );
                        }}
                        onPointerMove={hover.move}
                        onPointerLeave={hover.hide}
                        aria-label={`معاينة ${product.title}`}
                      >
                        {product.image_url ? (
                          <Image
                            src={product.image_url}
                            alt=""
                            fill
                            className="object-cover transition duration-150 hover:scale-105"
                            sizes="56px"
                          />
                        ) : (
                          <Package className="absolute inset-0 m-auto size-6 text-muted-foreground/60" />
                        )}
                      </button>
                      <button
                        type="button"
                        className="min-w-0 text-start"
                        onClick={(event) => {
                          event.stopPropagation();
                          onPreview(product);
                        }}
                      >
                        <span className="line-clamp-2 font-semibold leading-5 hover:text-primary">
                          {product.title}
                        </span>
                        <span className="mt-1 block truncate text-xs text-muted-foreground">
                          {[product.category, product.store_name].filter(Boolean).join(" · ") ||
                            product.aliexpress_product_id ||
                            product.id}
                        </span>
                      </button>
                    </div>
                  </td>
                ) : null}
                {show("price") ? (
                  <td className={`${cellPadding} font-medium tabular-nums`}>
                    {formatMoney(product.price, product.currency)}
                  </td>
                ) : null}
                {show("rating") ? (
                  <td className={`${cellPadding} tabular-nums`}>
                    <span aria-hidden>⭐ </span>
                    {product.rating.toFixed(2)}
                  </td>
                ) : null}
                {show("sales") ? (
                  <td className={`${cellPadding} tabular-nums`}>
                    {formatCompactNumber(product.sales)}
                  </td>
                ) : null}
                {show("score") ? (
                  <td
                    className={cellPadding}
                    onClick={(event) => event.stopPropagation()}
                    onPointerDown={(event) => event.stopPropagation()}
                  >
                    <ProductAiScoreCell product={product} />
                  </td>
                ) : null}
                {show("status") ? (
                  <td className={cellPadding}>
                    <div className="space-y-1.5">
                      <Badge tone={product.status === "active" ? "success" : "neutral"}>
                        {productStatusLabels[product.status]}
                      </Badge>
                      <ProductHealthBadges state={pipelineState} />
                    </div>
                  </td>
                ) : null}
                {show("actions") ? (
                  <td
                    className={`${cellPadding} text-center`}
                    onClick={(event) => event.stopPropagation()}
                    onPointerDown={(event) => event.stopPropagation()}
                  >
                    <ProductActionsMenu
                      product={product}
                      canDelete={canManage}
                      onPreview={() => onPreview(product)}
                      onGenerate={() => onGenerate(product)}
                      onDelete={() => onDelete(product)}
                    />
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

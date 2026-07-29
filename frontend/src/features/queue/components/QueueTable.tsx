"use client";

import Image from "next/image";
import { Package, Send } from "lucide-react";
import {
  ProductImageHoverPreview,
  useProductImageHover,
} from "@/components/common/ProductImageHoverPreview";
import { Badge, Button } from "@/components/ui/primitives";
import type { Channel } from "@/features/channels/types/api";
import type { Product } from "@/features/products/types/api";
import { formatQueueSchedule, getQueueHealth } from "../lib/operations";
import type {
  QueueItem,
  QueuePublishFailure,
  QueueTableDensity,
} from "../types/api";
import { QueueActionsMenu } from "./QueueActionsMenu";
import { QueueHealthBadge } from "./QueueHealthBadge";

export function QueueTable({
  items,
  selectedIds,
  allSelected,
  density,
  productsById,
  channelsById,
  publishingIds,
  failures,
  onToggle,
  onToggleAll,
  onView,
  onOpenProduct,
  onSchedule,
  onPublish,
  onOpenAi,
  onDelete,
}: {
  items: QueueItem[];
  selectedIds: string[];
  allSelected: boolean;
  density: QueueTableDensity;
  productsById: ReadonlyMap<string, Product>;
  channelsById: ReadonlyMap<string, Channel>;
  publishingIds: ReadonlySet<string>;
  failures: Readonly<Record<string, QueuePublishFailure>>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onView: (item: QueueItem) => void;
  onOpenProduct: (productId: string) => void;
  onSchedule: (item: QueueItem) => void;
  onPublish: (item: QueueItem) => void;
  onOpenAi: (item: QueueItem) => void;
  onDelete: (item: QueueItem) => void;
}) {
  const hover = useProductImageHover();
  const padding = density === "compact" ? "px-3 py-2" : "px-4 py-3";

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full min-w-[1120px] table-fixed text-sm">
        <thead className="bg-muted/60 text-right text-muted-foreground">
          <tr>
            <th className={`${padding} w-12`}>
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                aria-label="تحديد كل منشورات الصفحة"
              />
            </th>
            <th className={`${padding} w-[28%]`}>المنتج</th>
            <th className={`${padding} w-[17%]`}>القناة المستهدفة</th>
            <th className={`${padding} w-[14%]`}>الموعد</th>
            <th className={`${padding} w-[11%]`}>حالة النشر</th>
            <th className={`${padding} w-[12%]`}>سلامة العملية</th>
            <th className={`${padding} w-[18%]`}>الإجراءات</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item) => {
            const product = item.product_id ? productsById.get(item.product_id) : undefined;
            const channel = item.channel_id ? channelsById.get(item.channel_id) : undefined;
            const publishing = publishingIds.has(item.id);
            const failure = failures[item.id];
            const health = getQueueHealth(item, { publishing, failure });
            const schedule = formatQueueSchedule(item);
            const imageUrl = item.image_url ?? product?.image_url ?? null;
            const title = item.title ?? product?.title ?? "منشور بدون عنوان";
            const selected = selectedIds.includes(item.id);
            const originalUrl =
              product?.affiliate_url ?? product?.product_url ?? item.button_url;

            return (
              <tr
                key={item.id}
                className="cursor-pointer align-middle transition hover:bg-muted/35"
                onClick={() => onView(item)}
              >
                <td className={padding} onClick={(event) => event.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggle(item.id)}
                    onClick={(event) => event.stopPropagation()}
                    aria-label={`تحديد ${title}`}
                  />
                </td>
                <td className={padding}>
                  <div className="flex min-w-0 items-center gap-3">
                    <button
                      type="button"
                      className="relative size-12 shrink-0 overflow-hidden rounded-lg bg-muted"
                      disabled={!item.product_id}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (item.product_id) onOpenProduct(item.product_id);
                      }}
                      onPointerEnter={(event) => {
                        if (!imageUrl || !product) return;
                        hover.show(
                          {
                            src: imageUrl,
                            title,
                            price: product.price,
                            currency: product.currency,
                            discount: product.discount,
                          },
                          event,
                        );
                      }}
                      onPointerMove={hover.move}
                      onPointerLeave={hover.hide}
                      aria-label={item.product_id ? `فتح ${title}` : undefined}
                    >
                      {imageUrl ? (
                        <Image
                          src={imageUrl}
                          alt=""
                          fill
                          className="object-cover"
                          sizes="48px"
                        />
                      ) : (
                        <Package className="absolute inset-0 m-auto size-6 text-muted-foreground/60" />
                      )}
                    </button>
                    <button
                      type="button"
                      className="min-w-0 text-start disabled:cursor-default"
                      disabled={!item.product_id}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (item.product_id) onOpenProduct(item.product_id);
                      }}
                    >
                      <span className="line-clamp-2 font-semibold leading-5 hover:text-primary">
                        {title}
                      </span>
                      <span className="mt-1 block truncate text-xs text-muted-foreground">
                        {[product?.category, product?.store_name].filter(Boolean).join(" · ") ||
                          "محتوى نشر مستقل"}
                      </span>
                    </button>
                  </div>
                </td>
                <td className={padding}>
                  {channel ? (
                    <span className="inline-flex items-center gap-2 rounded-full bg-blue-500/10 px-2.5 py-1 text-xs text-blue-700 dark:text-blue-300">
                      <Send className="size-3.5" />
                      Telegram •{" "}
                      {channel.title ?? channel.username ?? channel.telegram_channel_id}
                    </span>
                  ) : (
                    <Badge tone="warning">بدون قناة</Badge>
                  )}
                </td>
                <td className={padding} onClick={(event) => event.stopPropagation()}>
                  <button
                    type="button"
                    className="rounded-md p-1 text-start hover:bg-muted"
                    onClick={() => onSchedule(item)}
                  >
                    <span className="block font-medium">{schedule.primary}</span>
                    {schedule.secondary ? (
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {schedule.secondary}
                      </span>
                    ) : null}
                  </button>
                </td>
                <td className={padding}>
                  <QueueStatusBadge item={item} publishing={publishing} failed={Boolean(failure)} />
                </td>
                <td className={padding} onClick={(event) => event.stopPropagation()}>
                  <QueueHealthBadge health={health} failure={failure} />
                </td>
                <td className={padding} onClick={(event) => event.stopPropagation()}>
                  <div className="flex items-center gap-1.5">
                    <Button
                      type="button"
                      className="h-8 px-2.5"
                      disabled={item.status === "published" || publishing}
                      loading={publishing}
                      onClick={() => onPublish(item)}
                    >
                      نشر الآن
                    </Button>
                    <QueueActionsMenu
                      originalUrl={originalUrl}
                      canOpenAi={Boolean(item.product_id || item.button_url)}
                      onView={() => onView(item)}
                      onReschedule={() => onSchedule(item)}
                      onOpenAi={() => onOpenAi(item)}
                      onDelete={() => onDelete(item)}
                    />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <ProductImageHoverPreview payload={hover.payload} />
    </div>
  );
}

function QueueStatusBadge({
  item,
  publishing,
  failed,
}: {
  item: QueueItem;
  publishing: boolean;
  failed: boolean;
}) {
  if (publishing) return <Badge tone="info">قيد النشر</Badge>;
  if (failed) return <Badge tone="error">فشل</Badge>;
  if (item.status === "published") return <Badge tone="success">منشور</Badge>;
  if (item.status === "scheduled") return <Badge tone="info">مجدول</Badge>;
  if (item.status === "queued") return <Badge tone="info">في الانتظار</Badge>;
  return <Badge tone="neutral">مسودة</Badge>;
}

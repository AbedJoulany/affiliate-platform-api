"use client";

import type { ReactNode } from "react";
import Image from "next/image";
import { CalendarClock, Package, Send, Sparkles } from "lucide-react";
import { Badge, Button, Drawer } from "@/components/ui/primitives";
import type { Channel } from "@/features/channels/types/api";
import type { Product } from "@/features/products/types/api";
import { formatQueueSchedule, getQueueHealth } from "../lib/operations";
import type { QueueItem, QueuePublishFailure } from "../types/api";
import { QueueHealthBadge } from "./QueueHealthBadge";

export function QueueDetailsDrawer({
  item,
  product,
  channel,
  publishing,
  failure,
  open,
  onClose,
  onPublish,
  onSchedule,
  onOpenAi,
  timelineSlot,
}: {
  item: QueueItem | null;
  product: Product | null;
  channel: Channel | null;
  publishing: boolean;
  failure?: QueuePublishFailure;
  open: boolean;
  onClose: () => void;
  onPublish: (item: QueueItem) => void;
  onSchedule: (item: QueueItem) => void;
  onOpenAi: (item: QueueItem) => void;
  /** Reserved for a future persisted Publishing Timeline. */
  timelineSlot?: ReactNode;
}) {
  const health = item
    ? getQueueHealth(item, { publishing, failure })
    : "missing_channel";
  const schedule = item ? formatQueueSchedule(item) : null;
  const imageUrl = item?.image_url ?? product?.image_url ?? null;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="تفاصيل عملية النشر"
      className="max-w-xl"
      footer={
        item ? (
          <div className="grid gap-2 sm:grid-cols-3">
            <Button
              disabled={item.status === "published" || publishing}
              loading={publishing}
              onClick={() => onPublish(item)}
            >
              نشر الآن
            </Button>
            <Button variant="outline" onClick={() => onSchedule(item)}>
              <CalendarClock className="size-4" />
              جدولة
            </Button>
            <Button
              variant="secondary"
              disabled={!item.product_id && !item.button_url}
              onClick={() => onOpenAi(item)}
            >
              <Sparkles className="size-4" />
              AI Studio
            </Button>
          </div>
        ) : null
      }
    >
      {item ? (
        <div className="space-y-5">
          <div className="flex items-start gap-3">
            <div className="relative size-20 shrink-0 overflow-hidden rounded-lg bg-muted">
              {imageUrl ? (
                <Image src={imageUrl} alt="" fill className="object-cover" sizes="80px" />
              ) : (
                <Package className="absolute inset-0 m-auto size-8 text-muted-foreground/60" />
              )}
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold leading-6">
                {item.title ?? product?.title ?? "منشور بدون عنوان"}
              </h3>
              <div className="mt-2">
                <QueueHealthBadge health={health} failure={failure} />
              </div>
            </div>
          </div>

          <dl className="grid gap-3 sm:grid-cols-2">
            <Info
              label="القناة"
              value={
                channel
                  ? `Telegram • ${
                      channel.title ?? channel.username ?? channel.telegram_channel_id
                    }`
                  : "غير محددة"
              }
              icon={<Send />}
            />
            <Info
              label="الموعد"
              value={
                schedule?.secondary
                  ? `${schedule.primary} • ${schedule.secondary}`
                  : schedule?.primary ?? "غير مجدول"
              }
              icon={<CalendarClock />}
            />
          </dl>

          <section>
            <h4 className="mb-2 text-sm font-semibold">معاينة المحتوى</h4>
            <div className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-muted/20 p-4 text-sm leading-7">
              {item.content}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              المحتوى للمعاينة فقط. التحرير وإعادة التوليد متاحان في AI Studio.
            </p>
          </section>

          <dl className="space-y-2 rounded-md border border-border p-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">الحالة المحفوظة</dt>
              <dd>{item.status}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">معرف رسالة Telegram</dt>
              <dd>{item.telegram_message_id ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">آخر تحديث</dt>
              <dd>
                {new Intl.DateTimeFormat("ar", {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(item.updated_at))}
              </dd>
            </div>
          </dl>

          {timelineSlot}
        </div>
      ) : null}
    </Drawer>
  );
}

function Info({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground [&_svg]:size-4">
        {icon}
        {label}
      </div>
      <p className="mt-1 font-medium">{value}</p>
    </div>
  );
}

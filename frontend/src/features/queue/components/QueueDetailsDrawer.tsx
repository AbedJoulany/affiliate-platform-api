"use client";

import { useState, type ReactNode } from "react";
import Image from "next/image";
import { CalendarClock, Globe2, Package, Send, Sparkles } from "lucide-react";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Badge, Button, Drawer } from "@/components/ui/primitives";
import type { Channel, FacebookPage } from "@/features/channels/types/api";
import type { Product } from "@/features/products/types/api";
import { useQueuePublishAttempts } from "../hooks/useQueue";
import {
  formatAttemptStatus,
  formatQueueSchedule,
  getQueueHealth,
  formatQueueStatus,
  resolveQueueFailure,
} from "../lib/operations";
import {
  getQueueDestination,
  isAmbiguousFacebookAttempt,
} from "../lib/destination";
import type { QueueItem, QueuePublishFailure } from "../types/api";
import type { PublishOptions } from "../hooks/useQueue";
import { QueueHealthBadge } from "./QueueHealthBadge";

export function QueueDetailsDrawer({
  item,
  product,
  channel,
  facebookPage,
  publishing,
  clientFailure,
  open,
  onClose,
  onPublish,
  onRetry,
  onSchedule,
  onOpenAi,
  timelineSlot,
}: {
  item: QueueItem | null;
  product: Product | null;
  channel: Channel | null;
  facebookPage: FacebookPage | null;
  publishing: boolean;
  /** Short-lived client fallback until backend summary enrichment arrives. */
  clientFailure?: QueuePublishFailure;
  open: boolean;
  onClose: () => void;
  onPublish: (item: QueueItem) => void;
  onRetry: (item: QueueItem, options?: PublishOptions) => void;
  onSchedule: (item: QueueItem) => void;
  onOpenAi: (item: QueueItem) => void;
  /** Reserved for a future persisted Publishing Timeline. */
  timelineSlot?: ReactNode;
}) {
  const [ambiguousConfirmationOpen, setAmbiguousConfirmationOpen] = useState(false);
  const attemptsQuery = useQueuePublishAttempts(item?.id ?? null, open && Boolean(item));
  const latestAttempt =
    attemptsQuery.data?.items[0] ?? item?.last_attempt ?? null;
  const attemptFailure =
    latestAttempt &&
    (latestAttempt.status === "failed" || latestAttempt.status === "ambiguous")
      ? {
          message:
            latestAttempt.error_message ?? latestAttempt.error_code ?? "فشل النشر",
          occurredAt: latestAttempt.occurred_at,
        }
      : undefined;
  const failure = item
    ? attemptFailure ?? resolveQueueFailure(item, clientFailure)
    : undefined;
  const displayItem = item && latestAttempt ? { ...item, last_attempt: latestAttempt } : item;
  const health = item && displayItem
    ? getQueueHealth(displayItem, { publishing, failure })
    : "missing_channel";
  const schedule = item ? formatQueueSchedule(item) : null;
  const imageUrl = item?.image_url ?? product?.image_url ?? null;
  const isFailed = item?.status === "failed";
  const ambiguousAttempt = Boolean(
    item && isAmbiguousFacebookAttempt(item, latestAttempt),
  );
  const destination = item
    ? getQueueDestination(item, channel, facebookPage)
    : null;
  const canRetry = Boolean(item && item.status !== "published");

  return (
    <>
      <Drawer
      open={open}
      onClose={onClose}
      title="تفاصيل عملية النشر"
      className="max-w-xl"
      footer={
        item ? (
          <div className="grid gap-2 sm:grid-cols-3">
            <Button
              disabled={!canRetry || publishing}
              loading={publishing}
              onClick={() => {
                if (ambiguousAttempt) {
                  setAmbiguousConfirmationOpen(true);
                } else if (isFailed || failure) {
                  onRetry(item);
                } else {
                  onPublish(item);
                }
              }}
            >
              {ambiguousAttempt
                ? "مراجعة وإعادة المحاولة"
                : isFailed || failure
                  ? "إعادة المحاولة"
                  : "نشر الآن"}
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
              {(item.retry_count ?? 0) > 0 ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  محاولات: {item.retry_count?.toLocaleString("ar")}
                </p>
              ) : null}
            </div>
          </div>

          <dl className="grid gap-3 sm:grid-cols-2">
            <Info
              label="الوجهة"
              value={
                destination
                  ? `${destination.label} • ${
                      destination.name ?? destination.identity ?? "غير متاحة"
                    }`
                  : "غير محددة"
              }
              icon={destination?.provider === "facebook" ? <Globe2 /> : <Send />}
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

          <section>
            <h4 className="mb-2 text-sm font-semibold">سجل محاولات النشر</h4>
            {attemptsQuery.isPending ? (
              <p className="text-sm text-muted-foreground">جاري تحميل السجل…</p>
            ) : attemptsQuery.isError ? (
              <p className="text-sm text-destructive" role="alert">
                تعذر تحميل سجل المحاولات.
              </p>
            ) : (attemptsQuery.data?.items.length ?? 0) === 0 ? (
              <p className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">
                لا توجد محاولات مسجّلة بعد.
              </p>
            ) : (
              <ul className="space-y-2">
                {attemptsQuery.data?.items.map((attempt) => (
                  <li
                    key={`${attempt.attempt_number}-${attempt.occurred_at}`}
                    className="rounded-md border border-border p-3 text-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">
                        محاولة {attempt.attempt_number.toLocaleString("ar")}
                      </span>
                      <Badge
                        tone={
                          attempt.status === "succeeded"
                            ? "success"
                            : attempt.status === "failed"
                              ? "error"
                              : attempt.status === "ambiguous"
                                ? "warning"
                                : "info"
                        }
                      >
                        {formatAttemptStatus(attempt.status)}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {new Intl.DateTimeFormat("ar", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      }).format(new Date(attempt.occurred_at))}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      المزوّد: {attempt.provider === "facebook" ? "Facebook" : "Telegram"}
                    </p>
                    {(attempt.status === "failed" || attempt.status === "ambiguous") &&
                    (attempt.error_message || attempt.error_code) ? (
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        {attempt.error_message ?? attempt.error_code}
                      </p>
                    ) : null}
                    {attempt.provider_message_ref ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        مرجع المزود: {attempt.provider_message_ref}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              السجل للقراءة فقط. النتائج غير المؤكدة تتطلب فحص صفحة Facebook قبل تأكيد إعادة المحاولة.
            </p>
          </section>

          <dl className="space-y-2 rounded-md border border-border p-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">الحالة المحفوظة</dt>
              <dd>{formatQueueStatus(item.status)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">حالة آخر محاولة</dt>
              <dd>{latestAttempt ? formatAttemptStatus(latestAttempt.status) : "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">مرجع المزود</dt>
              <dd>{latestAttempt?.provider_message_ref ?? "—"}</dd>
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
      <ConfirmDialog
      open={ambiguousConfirmationOpen}
      title="إعادة محاولة نشر غير مؤكدة؟"
      message={`افحص صفحة Facebook أولاً؛ قد يكون Meta قد قبل المنشور بالفعل. إذا وجدته منشوراً فلا تعاود المحاولة. تأكيد الإعادة قد ينشئ منشوراً مكرراً${destination?.name ? ` على صفحة ${destination.name}` : ""}.`}
      confirmLabel="تأكيد إعادة المحاولة"
      busy={publishing}
      onCancel={() => setAmbiguousConfirmationOpen(false)}
      onConfirm={() => {
        if (!item) return;
        setAmbiguousConfirmationOpen(false);
        onRetry(item, { confirmAmbiguous: true });
      }}
      />
    </>
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

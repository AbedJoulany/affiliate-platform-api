"use client";

import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Send } from "lucide-react";
import { useForm, type Resolver } from "react-hook-form";
import { Button, Input, Select } from "@/components/ui/primitives";
import type { Channel } from "@/features/channels/types/api";
import { getSchedulePreset } from "../lib/operations";
import {
  queueSchedulingSchema,
  type QueueSchedulingFormValues,
} from "../lib/schemas";

/** Form working values: both fields are always present in the UI. */
type QueueSchedulingFormFields = {
  intent: QueueSchedulingFormValues["intent"];
  channelId: string;
  scheduledAt: string;
};

export type QueueScheduleSubmitValues = Extract<
  QueueSchedulingFormValues,
  { intent: "schedule" }
>;
export type QueuePublishNowSubmitValues = Extract<
  QueueSchedulingFormValues,
  { intent: "publish_now" }
>;

export function QueueSchedulingDialog({
  open,
  itemCount,
  defaultValues,
  channels,
  busy,
  onSchedule,
  onPublishNow,
  onClose,
}: {
  open: boolean;
  itemCount: number;
  defaultValues: { channelId: string; scheduledAt: string };
  channels: Channel[];
  busy: boolean;
  onSchedule: (values: QueueScheduleSubmitValues) => void;
  onPublishNow: (values: QueuePublishNowSubmitValues) => void;
  onClose: () => void;
}) {
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<QueueSchedulingFormFields, unknown, QueueSchedulingFormValues>({
    resolver: zodResolver(queueSchedulingSchema) as Resolver<
      QueueSchedulingFormFields,
      unknown,
      QueueSchedulingFormValues
    >,
    defaultValues: {
      intent: "schedule",
      channelId: defaultValues.channelId,
      scheduledAt: defaultValues.scheduledAt,
    },
    mode: "onTouched",
  });

  useEffect(() => {
    if (!open) return;
    reset({
      intent: "schedule",
      channelId: defaultValues.channelId,
      scheduledAt: defaultValues.scheduledAt,
    });
  }, [open, defaultValues.channelId, defaultValues.scheduledAt, reset]);

  const channelId = watch("channelId");
  const scheduledAt = watch("scheduledAt");

  const setPreset = (preset: "hour" | "tomorrow_morning" | "tomorrow_evening") => {
    setValue("scheduledAt", toDateTimeLocal(getSchedulePreset(preset)), {
      shouldValidate: true,
      shouldTouch: true,
    });
  };

  const submitWithIntent = (intent: QueueSchedulingFormFields["intent"]) => {
    setValue("intent", intent);
    void handleSubmit((values) => {
      if (values.intent === "schedule") {
        onSchedule(values);
        return;
      }
      onPublishNow(values);
    })();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        className="w-full max-w-lg rounded-xl border border-border bg-surface p-5 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="queue-schedule-title"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="queue-schedule-title" className="text-lg font-semibold">
              إعداد عملية النشر
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {itemCount.toLocaleString("ar")} منشور محدد
            </p>
          </div>
          <Send className="size-5 text-primary" />
        </div>

        <div className="mt-5 space-y-4">
          <div>
            <label className="mb-1.5 block text-sm" htmlFor="queue-channel">
              القناة المستهدفة
            </label>
            <Select
              id="queue-channel"
              aria-invalid={!!errors.channelId}
              {...register("channelId")}
            >
              <option value="">اختر قناة Telegram</option>
              {channels
                .filter((channel) => channel.is_active && channel.can_post_messages)
                .map((channel) => (
                  <option key={channel.id} value={channel.id}>
                    {channel.title ?? channel.username ?? channel.telegram_channel_id}
                  </option>
                ))}
            </Select>
            {errors.channelId && (
              <p className="mt-1 text-sm text-destructive">{errors.channelId.message}</p>
            )}
          </div>

          <div>
            <p className="mb-1.5 text-sm">اختصارات الجدولة</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <Button type="button" variant="outline" onClick={() => setPreset("hour")}>
                بعد ساعة
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setPreset("tomorrow_morning")}
              >
                صباح الغد
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setPreset("tomorrow_evening")}
              >
                مساء الغد
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={!channelId || busy}
                loading={busy}
                onClick={() => submitWithIntent("publish_now")}
              >
                نشر الآن
              </Button>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm" htmlFor="queue-custom-date">
              تاريخ ووقت مخصص
            </label>
            <Input
              id="queue-custom-date"
              type="datetime-local"
              min={toDateTimeLocal(new Date())}
              aria-invalid={!!errors.scheduledAt}
              {...register("scheduledAt")}
            />
            {errors.scheduledAt && (
              <p className="mt-1 text-sm text-destructive">{errors.scheduledAt.message}</p>
            )}
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" disabled={busy} onClick={onClose}>
            إلغاء
          </Button>
          <Button
            type="button"
            disabled={!channelId || !scheduledAt || busy}
            loading={busy}
            onClick={() => submitWithIntent("schedule")}
          >
            حفظ الجدولة
          </Button>
        </div>
      </div>
    </div>
  );
}

function toDateTimeLocal(date: Date): string {
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

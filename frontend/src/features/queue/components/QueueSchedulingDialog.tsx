"use client";

import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Send } from "lucide-react";
import { useForm, type Resolver } from "react-hook-form";
import { Button, Input } from "@/components/ui/primitives";
import type { Channel, FacebookPage } from "@/features/channels/types/api";
import { getSchedulePreset } from "../lib/operations";
import {
  queueSchedulingSchema,
  type QueueSchedulingFormValues,
} from "../lib/schemas";
import {
  PublishingDestinationSelector,
  type DestinationSelection,
} from "./PublishingDestinationSelector";

/** Form working values: both fields are always present in the UI. */
type QueueSchedulingFormFields = {
  intent: QueueSchedulingFormValues["intent"];
  destinationId: string;
  scheduledAt: string;
};

export type QueueScheduleSubmitValues = Extract<
  QueueSchedulingFormValues,
  { intent: "schedule" }
> & { destination: DestinationSelection };
export type QueuePublishNowSubmitValues = Extract<
  QueueSchedulingFormValues,
  { intent: "publish_now" }
> & { destination: DestinationSelection };

export function QueueSchedulingDialog({
  open,
  itemCount,
  defaultValues,
  channels,
  facebookPages,
  preserveDestinations = false,
  busy,
  onSchedule,
  onPublishNow,
  onClose,
}: {
  open: boolean;
  itemCount: number;
  defaultValues: { destination: DestinationSelection; scheduledAt: string };
  channels: Channel[];
  facebookPages: FacebookPage[];
  preserveDestinations?: boolean;
  busy: boolean;
  onSchedule: (values: QueueScheduleSubmitValues) => void;
  onPublishNow: (values: QueuePublishNowSubmitValues) => void;
  onClose: () => void;
}) {
  const [destination, setDestination] = useState<DestinationSelection>(
    defaultValues.destination,
  );
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    trigger,
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
      destinationId:
        defaultValues.destination.channelId ?? defaultValues.destination.facebookPageId ?? "",
      scheduledAt: defaultValues.scheduledAt,
    },
    mode: "onTouched",
  });

  useEffect(() => {
    if (!open) return;
    reset({
      intent: "schedule",
      destinationId:
        defaultValues.destination.channelId ?? defaultValues.destination.facebookPageId ?? "",
      scheduledAt: defaultValues.scheduledAt,
    });
    setDestination(defaultValues.destination);
  }, [open, defaultValues.destination, defaultValues.scheduledAt, reset]);

  const destinationId = watch("destinationId");
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
        onSchedule({ ...values, destination });
        return;
      }
      onPublishNow({ ...values, destination });
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
          {preserveDestinations ? (
            <p className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900 dark:bg-blue-950/30 dark:text-blue-200">
              وجهات المنشورات المحددة محفوظة لكل عنصر ولن يتم استبدالها في العملية الجماعية.
            </p>
          ) : (
            <div>
              <input type="hidden" {...register("destinationId")} />
              <PublishingDestinationSelector
                value={destination}
                channels={channels}
                pages={facebookPages}
                onBlur={() => void trigger("destinationId")}
                onChange={(next) => {
                  setDestination(next);
                  setValue(
                    "destinationId",
                    next.channelId ?? next.facebookPageId ?? "",
                    { shouldValidate: true, shouldTouch: true },
                  );
                }}
              />
              {errors.destinationId && (
                <p className="mt-1 text-sm text-destructive">
                  {errors.destinationId.message}
                </p>
              )}
            </div>
          )}

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
                disabled={!destinationId || busy}
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
            disabled={!destinationId || !scheduledAt || busy}
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

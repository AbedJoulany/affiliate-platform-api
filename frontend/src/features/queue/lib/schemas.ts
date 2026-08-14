import { z } from "zod";
import { QUEUE_STATUSES } from "../types/api";

export const QUEUE_SCHEDULE_INTENTS = ["schedule", "publish_now"] as const;

/** Reuses the existing queue status source of truth from `types/api.ts`. */
export const queueStatusSchema = z.enum(QUEUE_STATUSES);

const DATETIME_LOCAL_PATTERN = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

function parseDateTimeLocal(value: string): Date | null {
  const match = DATETIME_LOCAL_PATTERN.exec(value);
  if (!match) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

const channelIdSchema = z
  .string()
  .min(1, "القناة المستهدفة مطلوبة")
  .uuid("معرّف القناة غير صالح");

const scheduledAtSchema = z
  .string()
  .min(1, "تاريخ ووقت الجدولة مطلوب")
  .refine((value) => parseDateTimeLocal(value) !== null, {
    message: "أدخل تاريخًا ووقتًا صحيحين",
  })
  .refine(
    (value) => {
      const parsed = parseDateTimeLocal(value);
      return parsed !== null && parsed.getTime() >= Date.now();
    },
    { message: "لا يمكن جدولة وقت في الماضي" },
  );

/**
 * Form-domain schema for queue scheduling.
 * API serialization (`status`, ISO `scheduled_at`) stays in the submit mapper.
 */
export const queueSchedulingSchema = z.discriminatedUnion("intent", [
  z.object({
    intent: z.literal("schedule"),
    channelId: channelIdSchema,
    scheduledAt: scheduledAtSchema,
  }),
  z.object({
    intent: z.literal("publish_now"),
    channelId: channelIdSchema,
  }),
]);

export type QueueSchedulingFormValues = z.infer<typeof queueSchedulingSchema>;

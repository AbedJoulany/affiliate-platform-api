import { z } from "zod";
import {
  invalidDateTime,
  invalidUuid,
  requiredField,
} from "@/lib/validation/messages";
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

/**
 * Queue item → channel assignment at schedule/publish time.
 * Required UUID string. Empty placeholder ("اختر قناة Telegram") is invalid.
 * QueueItem.channel_id remains nullable at rest; this schema covers the
 * existing editable assignment field only.
 */
export const channelAssignmentSchema = z
  .string()
  .min(1, requiredField("القناة المستهدفة", { feminine: true }))
  .uuid(invalidUuid("معرّف القناة"));

export type ChannelAssignment = z.infer<typeof channelAssignmentSchema>;

const scheduledAtSchema = z
  .string()
  .min(1, requiredField("تاريخ ووقت الجدولة"))
  .refine((value) => parseDateTimeLocal(value) !== null, {
    message: invalidDateTime,
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
    channelId: channelAssignmentSchema,
    scheduledAt: scheduledAtSchema,
  }),
  z.object({
    intent: z.literal("publish_now"),
    channelId: channelAssignmentSchema,
  }),
]);

export type QueueSchedulingFormValues = z.infer<typeof queueSchedulingSchema>;

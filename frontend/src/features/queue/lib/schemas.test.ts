import { describe, expect, it } from "vitest";
import { QUEUE_STATUSES } from "../types/api";
import {
  channelAssignmentSchema,
  queueSchedulingSchema,
  queueStatusSchema,
} from "./schemas";

const VALID_CHANNEL_ID = "550e8400-e29b-41d4-a716-446655440000";
const FUTURE_LOCAL = "2099-06-15T14:30";
const PAST_LOCAL = "2020-01-15T09:00";

describe("channelAssignmentSchema", () => {
  it("accepts a valid channel UUID", () => {
    const result = channelAssignmentSchema.safeParse(VALID_CHANNEL_ID);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toBe(VALID_CHANNEL_ID);
    }
  });

  it("rejects an empty selection (placeholder must not become an API value)", () => {
    const result = channelAssignmentSchema.safeParse("");
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("القناة المستهدفة مطلوبة");
    }
  });

  it("rejects null and undefined", () => {
    expect(channelAssignmentSchema.safeParse(null).success).toBe(false);
    expect(channelAssignmentSchema.safeParse(undefined).success).toBe(false);
  });

  it("rejects a malformed channel ID", () => {
    const result = channelAssignmentSchema.safeParse("not-a-uuid");
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("معرّف القناة غير صالح");
    }
  });

  it("rejects a telegram handle that is not a Channel.id", () => {
    expect(channelAssignmentSchema.safeParse("@mychannel").success).toBe(false);
    expect(channelAssignmentSchema.safeParse("-100123").success).toBe(false);
  });
});

describe("queueSchedulingSchema", () => {
  it("accepts a valid schedule payload", () => {
    const result = queueSchedulingSchema.safeParse({
      intent: "schedule",
      channelId: VALID_CHANNEL_ID,
      scheduledAt: FUTURE_LOCAL,
    });
    expect(result.success).toBe(true);
    if (result.success && result.data.intent === "schedule") {
      expect(result.data.channelId).toBe(VALID_CHANNEL_ID);
      expect(result.data.scheduledAt).toBe(FUTURE_LOCAL);
    }
  });

  it("rejects a schedule payload missing scheduledAt", () => {
    const result = queueSchedulingSchema.safeParse({
      intent: "schedule",
      channelId: VALID_CHANNEL_ID,
    });
    expect(result.success).toBe(false);
  });

  it("rejects a past scheduledAt", () => {
    const result = queueSchedulingSchema.safeParse({
      intent: "schedule",
      channelId: VALID_CHANNEL_ID,
      scheduledAt: PAST_LOCAL,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((issue) => issue.message);
      expect(messages).toContain("لا يمكن جدولة وقت في الماضي");
    }
  });

  it("rejects a malformed scheduledAt without throwing", () => {
    const result = queueSchedulingSchema.safeParse({
      intent: "schedule",
      channelId: VALID_CHANNEL_ID,
      scheduledAt: "not-a-datetime",
    });
    expect(result.success).toBe(false);
  });

  it("accepts a valid publish_now payload without scheduledAt", () => {
    const result = queueSchedulingSchema.safeParse({
      intent: "publish_now",
      channelId: VALID_CHANNEL_ID,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.intent).toBe("publish_now");
      expect(result.data).not.toHaveProperty("scheduledAt");
    }
  });

  it("rejects missing channelId on both intents", () => {
    const schedule = queueSchedulingSchema.safeParse({
      intent: "schedule",
      scheduledAt: FUTURE_LOCAL,
    });
    const publishNow = queueSchedulingSchema.safeParse({
      intent: "publish_now",
    });
    expect(schedule.success).toBe(false);
    expect(publishNow.success).toBe(false);
  });

  it("rejects an empty channelId", () => {
    const result = queueSchedulingSchema.safeParse({
      intent: "publish_now",
      channelId: "",
    });
    expect(result.success).toBe(false);
  });

  it("rejects a malformed channel UUID", () => {
    const result = queueSchedulingSchema.safeParse({
      intent: "schedule",
      channelId: "not-a-uuid",
      scheduledAt: FUTURE_LOCAL,
    });
    expect(result.success).toBe(false);
  });

  it("rejects an invalid intent", () => {
    const result = queueSchedulingSchema.safeParse({
      intent: "queued",
      channelId: VALID_CHANNEL_ID,
      scheduledAt: FUTURE_LOCAL,
    });
    expect(result.success).toBe(false);
  });

  it("rejects a non-object payload without throwing", () => {
    expect(queueSchedulingSchema.safeParse(null).success).toBe(false);
    expect(queueSchedulingSchema.safeParse("scheduled").success).toBe(false);
    expect(queueSchedulingSchema.safeParse(undefined).success).toBe(false);
  });
});

describe("queueStatusSchema", () => {
  it("accepts existing queue statuses", () => {
    for (const status of QUEUE_STATUSES) {
      expect(queueStatusSchema.safeParse(status).success).toBe(true);
    }
  });

  it("rejects an unknown status value", () => {
    expect(queueStatusSchema.safeParse("publishing").success).toBe(false);
  });
});

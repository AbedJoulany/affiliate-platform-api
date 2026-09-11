import { describe, expect, it } from "vitest";
import type { QueueItem } from "../types/api";
import { nextStatusAfterFailedRetry } from "./retry";

function item(overrides: Partial<QueueItem> = {}): QueueItem {
  return {
    id: "q-1",
    title: "فشل",
    content: "محتوى",
    status: "failed",
    scheduled_at: null,
    published_at: null,
    channel_id: "ch-1",
    product_id: null,
    image_url: null,
    button_text: null,
    button_url: null,
    telegram_message_id: null,
    created_at: "2026-09-07T09:00:00.000Z",
    updated_at: "2026-09-07T09:00:00.000Z",
    ...overrides,
  };
}

describe("nextStatusAfterFailedRetry", () => {
  it("returns queued when there is no future schedule", () => {
    expect(nextStatusAfterFailedRetry(item())).toEqual({ status: "queued" });
  });

  it("returns scheduled when the original schedule is still in the future", () => {
    const scheduledAt = new Date(Date.now() + 60 * 60 * 1000).toISOString();
    expect(nextStatusAfterFailedRetry(item({ scheduled_at: scheduledAt }))).toEqual({
      status: "scheduled",
      scheduled_at: scheduledAt,
    });
  });
});

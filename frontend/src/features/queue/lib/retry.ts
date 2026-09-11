import type { QueueItem, QueueUpdate } from "../types/api";

/** Move a terminal failed item back onto the existing publish path. */
export function nextStatusAfterFailedRetry(item: QueueItem): QueueUpdate {
  if (item.scheduled_at && new Date(item.scheduled_at).getTime() > Date.now()) {
    return { status: "scheduled", scheduled_at: item.scheduled_at };
  }
  return { status: "queued" };
}

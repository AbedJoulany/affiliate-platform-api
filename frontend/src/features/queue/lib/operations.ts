import type {
  QueueHealthStatus,
  QueueItem,
  QueuePublishFailure,
} from "../types/api";

/** Map QueueRead attempt summary → UI failure shape. */
export function failureFromQueueItem(
  item: QueueItem,
): QueuePublishFailure | undefined {
  const attempt = item.last_attempt;
  if (attempt?.status === "failed") {
    return {
      message:
        item.failure_reason ??
        attempt.error_message ??
        "فشل النشر",
      occurredAt: attempt.occurred_at,
    };
  }
  if (item.failure_reason) {
    return {
      message: item.failure_reason,
      occurredAt: attempt?.occurred_at ?? item.updated_at,
    };
  }
  return undefined;
}

/**
 * Prefer backend attempt summary; client map is rollout fallback only
 * until GET /queues/{id} enrichment lands.
 */
export function resolveQueueFailure(
  item: QueueItem,
  clientFallback?: QueuePublishFailure,
): QueuePublishFailure | undefined {
  return failureFromQueueItem(item) ?? clientFallback;
}

export function getQueueHealth(
  item: QueueItem,
  context: {
    publishing: boolean;
    failure?: QueuePublishFailure;
  },
): QueueHealthStatus {
  if (item.status === "published") return "published";
  if (context.publishing) return "publishing";
  if (context.failure) return "error";
  if (!item.channel_id) return "missing_channel";
  if (
    item.status === "draft" ||
    (item.status === "scheduled" && !item.scheduled_at)
  ) {
    return "missing_schedule";
  }
  return "ready";
}

export function isToday(value: string | null | undefined): boolean {
  if (!value) return false;
  const date = new Date(value);
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

export function getQueueOperationalStats(
  items: QueueItem[],
  publishingIds: ReadonlySet<string>,
  clientFailures: Readonly<Record<string, QueuePublishFailure>> = {},
) {
  let failedToday = 0;
  for (const item of items) {
    const failure = resolveQueueFailure(item, clientFailures[item.id]);
    if (failure && isToday(failure.occurredAt)) {
      failedToday += 1;
    }
  }

  return {
    queued: items.filter((item) => item.status === "queued").length,
    scheduled: items.filter((item) => item.status === "scheduled").length,
    publishing: publishingIds.size,
    publishedToday: items.filter(
      (item) => item.status === "published" && isToday(item.published_at),
    ).length,
    failedToday,
  };
}

export function formatQueueSchedule(item: QueueItem): {
  primary: string;
  secondary: string | null;
} {
  const value = item.scheduled_at ?? item.published_at;
  if (!value) return { primary: "غير مجدول", secondary: null };

  const date = new Date(value);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  const sameDay = (left: Date, right: Date) =>
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate();

  const dayLabel = sameDay(date, today)
    ? "اليوم"
    : sameDay(date, tomorrow)
      ? "غدًا"
      : new Intl.DateTimeFormat("ar", {
          day: "numeric",
          month: "short",
        }).format(date);

  return {
    primary: dayLabel,
    secondary: new Intl.DateTimeFormat("ar", {
      hour: "numeric",
      minute: "2-digit",
    }).format(date),
  };
}

export function getSchedulePreset(
  preset: "hour" | "tomorrow_morning" | "tomorrow_evening",
): Date {
  const date = new Date();
  if (preset === "hour") {
    date.setHours(date.getHours() + 1);
    return date;
  }
  date.setDate(date.getDate() + 1);
  date.setHours(preset === "tomorrow_morning" ? 9 : 18, 0, 0, 0);
  return date;
}

const ATTEMPT_STATUS_LABELS: Record<string, string> = {
  started: "بدأ",
  succeeded: "نجح",
  failed: "فشل",
};

export function formatAttemptStatus(status: string): string {
  return ATTEMPT_STATUS_LABELS[status] ?? status;
}

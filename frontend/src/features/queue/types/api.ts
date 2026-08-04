export const QUEUE_STATUSES = ["draft", "queued", "scheduled", "published"] as const;
export type QueueStatus = (typeof QUEUE_STATUSES)[number];

/** Attempt-scoped only — not a QueueStatus value. */
export const QUEUE_PUBLISH_ATTEMPT_STATUSES = [
  "started",
  "succeeded",
  "failed",
] as const;
export type QueuePublishAttemptStatus =
  (typeof QUEUE_PUBLISH_ATTEMPT_STATUSES)[number];

export interface QueuePublishAttempt {
  attempt_number: number;
  status: QueuePublishAttemptStatus | string;
  provider: string;
  occurred_at: string;
  error_code: string | null;
  error_message: string | null;
  provider_chat_id: string | null;
  provider_message_id: number | null;
}

export interface QueuePublishAttemptListResponse {
  queue_id: string;
  items: QueuePublishAttempt[];
  total: number;
}

export interface QueueItem {
  id: string;
  title: string | null;
  content: string;
  status: QueueStatus;
  scheduled_at: string | null;
  published_at: string | null;
  channel_id: string | null;
  product_id: string | null;
  image_url: string | null;
  button_text: string | null;
  button_url: string | null;
  telegram_message_id: number | null;
  created_at: string;
  updated_at: string;
  /** Populated on GET /queues/{id}; list responses default to null. */
  last_attempt?: QueuePublishAttempt | null;
  /** Latest failed attempt error_message when applicable. */
  failure_reason?: string | null;
  /** Latest attempt_number (0 when never attempted). */
  retry_count?: number;
}

export interface QueueListResponse {
  items: QueueItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface QueueCreate {
  title?: string;
  content: string;
  status: QueueStatus;
  scheduled_at?: string | null;
  channel_id?: string | null;
  product_id?: string | null;
  image_url?: string | null;
  button_text?: string | null;
  button_url?: string | null;
}

export type QueueUpdate = Partial<QueueCreate>;

export type QueueHealthStatus =
  | "ready"
  | "missing_schedule"
  | "missing_channel"
  | "publishing"
  | "published"
  | "error";

export type QueueWorkspaceSort =
  | "newest"
  | "oldest"
  | "schedule_asc"
  | "schedule_desc"
  | "status";

export type QueueTableDensity = "comfortable" | "compact";

export type QueuePublishFailure = {
  message: string;
  occurredAt: string;
};

export interface PublishQueueResponse {
  queue_id: string;
  telegram_message_id: number;
  chat_id: string;
  message_type: string;
  published_at: string;
}

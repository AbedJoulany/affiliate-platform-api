export const QUEUE_STATUSES = ["draft", "queued", "scheduled", "published"] as const;
export type QueueStatus = (typeof QUEUE_STATUSES)[number];

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

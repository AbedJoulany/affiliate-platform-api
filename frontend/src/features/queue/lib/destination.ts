import type { Channel, FacebookPage } from "@/features/channels/types/api";
import type { QueueItem, QueueProvider, QueuePublishAttempt } from "../types/api";

export function queueProvider(
  item: Pick<QueueItem, "provider"> | { provider?: QueueProvider | null },
): QueueProvider {
  // Older Telegram rows predate the additive provider field.
  return item.provider ?? "telegram";
}
export function isAmbiguousFacebookAttempt(
  item: Pick<QueueItem, "provider"> | { provider?: QueueProvider | null },
  attempt?: Pick<QueuePublishAttempt, "provider" | "status"> | null,
): boolean {
  return (
    queueProvider(item) === "facebook" &&
    attempt?.provider === "facebook" &&
    attempt.status === "ambiguous"
  );
}

export type QueueDestination = {
  provider: QueueProvider;
  label: string;
  name: string | null;
  identity: string | null;
  available: boolean;
};

type QueueDestinationInput = {
  provider?: QueueProvider | null;
  channel_id?: string | null;
  facebook_page_id?: string | null;
};

export function getQueueDestination(
  item: QueueDestinationInput,
  channel?: Channel | null,
  page?: FacebookPage | null,
): QueueDestination {
  const provider = queueProvider(item);
  if (provider === "facebook") {
    return {
      provider,
      label: "Facebook",
      name: page?.page_name ?? null,
      identity: page?.facebook_page_id ?? item.facebook_page_id ?? null,
      available: Boolean(page && page.is_active && page.validation_status === "valid"),
    };
  }

  return {
    provider: "telegram",
    label: "Telegram",
    name: channel?.title ?? channel?.username ?? null,
    identity: channel?.telegram_channel_id ?? item.channel_id ?? null,
    available: Boolean(channel?.is_active),
  };
}

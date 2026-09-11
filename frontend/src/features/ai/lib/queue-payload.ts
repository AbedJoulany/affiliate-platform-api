import type { QueueCreate } from "@/features/queue/types/api";

export const DEFAULT_AFFILIATE_BUTTON_TEXT = "اشتري الآن";

/** Persist the affiliate URL as the Telegram CTA. Never use product_url. */
export function resolveAffiliateCta(affiliateUrl?: string | null): {
  button_text?: string;
  button_url?: string;
} {
  if (!affiliateUrl) return {};
  return {
    button_text: DEFAULT_AFFILIATE_BUTTON_TEXT,
    button_url: affiliateUrl,
  };
}

export function buildAiQueueCreateInput(input: {
  content: string;
  status: Extract<QueueCreate["status"], "draft" | "queued" | "scheduled">;
  productId?: string | null;
  title?: string | null;
  channelId?: string | null;
  imageUrl?: string | null;
  affiliateUrl?: string | null;
  scheduledAt?: string | null;
}): QueueCreate {
  const cta = resolveAffiliateCta(input.affiliateUrl);
  return {
    content: input.content,
    status: input.status,
    ...(input.productId ? { product_id: input.productId } : {}),
    ...(input.title ? { title: input.title } : {}),
    ...(input.channelId ? { channel_id: input.channelId } : {}),
    ...(input.imageUrl ? { image_url: input.imageUrl } : {}),
    ...(input.scheduledAt ? { scheduled_at: input.scheduledAt } : {}),
    ...cta,
  };
}

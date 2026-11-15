import type { QueueCreate, QueueProvider } from "@/features/queue/types/api";

export const DEFAULT_AFFILIATE_BUTTON_TEXT = "اشتري الآن";

/** Persist the affiliate URL as the provider CTA. Never use product_url. */
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
  provider?: QueueProvider;
  channelId?: string | null;
  facebookPageId?: string | null;
  imageUrl?: string | null;
  affiliateUrl?: string | null;
  scheduledAt?: string | null;
}): QueueCreate {
  const cta = resolveAffiliateCta(input.affiliateUrl);
  const provider = input.provider ?? "telegram";
  return {
    content: input.content,
    status: input.status,
    ...(input.productId ? { product_id: input.productId } : {}),
    ...(input.title ? { title: input.title } : {}),
    provider,
    ...(provider === "telegram" && input.channelId
      ? { channel_id: input.channelId }
      : {}),
    ...(provider === "facebook" && input.facebookPageId
      ? { facebook_page_id: input.facebookPageId }
      : {}),
    ...(input.imageUrl ? { image_url: input.imageUrl } : {}),
    ...(input.scheduledAt ? { scheduled_at: input.scheduledAt } : {}),
    ...cta,
  };
}

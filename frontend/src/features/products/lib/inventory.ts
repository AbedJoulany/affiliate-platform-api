import type { QueueItem } from "@/features/queue/types/api";
import type { Product } from "../types/api";

export type ProductPipelineState = {
  hasContent: boolean;
  queued: boolean;
  published: boolean;
  lowScore: boolean;
};

export function indexQueueByProduct(items: QueueItem[]): Map<string, QueueItem[]> {
  const index = new Map<string, QueueItem[]>();
  for (const item of items) {
    if (!item.product_id) continue;
    const current = index.get(item.product_id) ?? [];
    current.push(item);
    index.set(item.product_id, current);
  }
  return index;
}

export function getProductPipelineState(
  product: Product,
  queueIndex: ReadonlyMap<string, QueueItem[]>,
): ProductPipelineState {
  const queueItems = queueIndex.get(product.id) ?? [];
  return {
    hasContent: queueItems.length > 0,
    queued: queueItems.some((item) =>
      ["queued", "scheduled", "published"].includes(item.status),
    ),
    published: queueItems.some((item) => item.status === "published"),
    lowScore: product.score < 55,
  };
}

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function getScoreQuality(score: number): {
  label: string;
  tone: "success" | "info" | "warning" | "error";
} {
  if (score >= 85) return { label: "ممتاز", tone: "success" };
  if (score >= 70) return { label: "إمكانات عالية", tone: "info" };
  if (score >= 55) return { label: "متوسط", tone: "warning" };
  return { label: "منخفض", tone: "error" };
}

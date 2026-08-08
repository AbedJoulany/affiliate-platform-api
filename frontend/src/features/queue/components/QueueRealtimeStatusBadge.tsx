"use client";

import { Badge } from "@/components/ui/primitives";
import type { QueueEventStreamStatus } from "../hooks/useQueueEventStream";

const STATUS_UI: Record<
  QueueEventStreamStatus,
  {
    label: string;
    tone: "success" | "info" | "warning" | "error" | "neutral";
    description: string;
  }
> = {
  connected: {
    label: "مباشر",
    tone: "success",
    description: "البث الحي متصل",
  },
  connecting: {
    label: "جاري الاتصال…",
    tone: "info",
    description: "جارٍ الاتصال بالبث الحي",
  },
  disconnected: {
    label: "غير متصل",
    tone: "warning",
    description: "البث الحي غير متصل — قائمة النشر تبقى قابلة للاستخدام",
  },
  error: {
    label: "البث متوقف",
    tone: "error",
    description: "تعذر استمرار البث الحي — قائمة النشر تبقى قابلة للاستخدام",
  },
};

/**
 * Subtle Queue workspace indicator for SSE health.
 * Does not block actions or claim global backend health.
 */
export function QueueRealtimeStatusBadge({
  status,
}: {
  status: QueueEventStreamStatus;
}) {
  const ui = STATUS_UI[status];

  return (
    <Badge
      tone={ui.tone}
      title={ui.description}
      aria-label={ui.description}
      role="status"
      className="shrink-0"
    >
      <span
        className="me-1.5 inline-block size-1.5 rounded-full bg-current"
        aria-hidden
      />
      {ui.label}
    </Badge>
  );
}

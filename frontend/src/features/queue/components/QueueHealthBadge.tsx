"use client";

import { useRef, useState } from "react";
import { Badge, Popover } from "@/components/ui/primitives";
import type { QueueHealthStatus, QueuePublishFailure } from "../types/api";

const HEALTH_META: Record<
  QueueHealthStatus,
  { label: string; tone: "success" | "info" | "warning" | "error" | "neutral" }
> = {
  ready: { label: "جاهز", tone: "success" },
  missing_schedule: { label: "ينقصه موعد", tone: "warning" },
  missing_channel: { label: "ينقصه قناة", tone: "warning" },
  publishing: { label: "قيد النشر", tone: "info" },
  published: { label: "منشور", tone: "success" },
  error: { label: "خطأ", tone: "error" },
};

export function QueueHealthBadge({
  health,
  failure,
}: {
  health: QueueHealthStatus;
  failure?: QueuePublishFailure;
}) {
  const meta = HEALTH_META[health];
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);

  if (health !== "error" || !failure) {
    return <Badge tone={meta.tone}>{meta.label}</Badge>;
  }

  return (
    <>
      <button
        ref={anchorRef}
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((previous) => !previous);
        }}
      >
        <Badge tone="error">خطأ · عرض السبب</Badge>
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchorRef}>
        <p className="text-sm font-semibold">فشل النشر</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{failure.message}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          {new Intl.DateTimeFormat("ar", {
            dateStyle: "medium",
            timeStyle: "short",
          }).format(new Date(failure.occurredAt))}
        </p>
      </Popover>
    </>
  );
}

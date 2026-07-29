"use client";

import { useEffect } from "react";
import { CheckCircle2, CircleAlert, X } from "lucide-react";

export function ToastOverlay({
  message,
  tone = "success",
  onDismiss,
  duration = 3500,
}: {
  message: string | null;
  tone?: "success" | "error";
  onDismiss: () => void;
  duration?: number;
}) {
  useEffect(() => {
    if (!message) return;
    const timeout = window.setTimeout(onDismiss, duration);
    return () => window.clearTimeout(timeout);
  }, [message, duration, onDismiss]);

  if (!message) return null;

  const Icon = tone === "success" ? CheckCircle2 : CircleAlert;
  return (
    <div className="pointer-events-none fixed inset-x-4 bottom-5 z-[70] flex justify-center">
      <div
        className={[
          "pointer-events-auto flex max-w-lg items-center gap-3 rounded-lg border bg-surface/95 px-4 py-3 text-sm shadow-xl backdrop-blur",
          tone === "success"
            ? "border-emerald-500/35 text-emerald-800 dark:text-emerald-200"
            : "border-red-500/35 text-red-700 dark:text-red-300",
        ].join(" ")}
        role={tone === "error" ? "alert" : "status"}
      >
        <Icon className="size-5 shrink-0" />
        <p className="font-medium">{message}</p>
        <button
          type="button"
          className="ms-2 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="إغلاق الإشعار"
          onClick={onDismiss}
        >
          <X className="size-4" />
        </button>
      </div>
    </div>
  );
}

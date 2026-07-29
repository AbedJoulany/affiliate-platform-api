"use client";

import { Send } from "lucide-react";
import { Button, Input, Select } from "@/components/ui/primitives";
import type { Channel } from "@/features/channels/types/api";
import { getSchedulePreset } from "../lib/operations";

export function QueueSchedulingDialog({
  open,
  itemCount,
  channelId,
  scheduledAt,
  channels,
  busy,
  onChannelChange,
  onScheduledAtChange,
  onPublishNow,
  onApply,
  onClose,
}: {
  open: boolean;
  itemCount: number;
  channelId: string;
  scheduledAt: string;
  channels: Channel[];
  busy: boolean;
  onChannelChange: (value: string) => void;
  onScheduledAtChange: (value: string) => void;
  onPublishNow: () => void;
  onApply: () => void;
  onClose: () => void;
}) {
  if (!open) return null;

  const setPreset = (preset: "hour" | "tomorrow_morning" | "tomorrow_evening") => {
    onScheduledAtChange(toDateTimeLocal(getSchedulePreset(preset)));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        className="w-full max-w-lg rounded-xl border border-border bg-surface p-5 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="queue-schedule-title"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="queue-schedule-title" className="text-lg font-semibold">
              إعداد عملية النشر
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {itemCount.toLocaleString("ar")} منشور محدد
            </p>
          </div>
          <Send className="size-5 text-primary" />
        </div>

        <div className="mt-5 space-y-4">
          <div>
            <label className="mb-1.5 block text-sm" htmlFor="queue-channel">
              القناة المستهدفة
            </label>
            <Select
              id="queue-channel"
              value={channelId}
              onChange={(event) => onChannelChange(event.target.value)}
            >
              <option value="">اختر قناة Telegram</option>
              {channels
                .filter((channel) => channel.is_active && channel.can_post_messages)
                .map((channel) => (
                  <option key={channel.id} value={channel.id}>
                    {channel.title ?? channel.username ?? channel.telegram_channel_id}
                  </option>
                ))}
            </Select>
          </div>

          <div>
            <p className="mb-1.5 text-sm">اختصارات الجدولة</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <Button type="button" variant="outline" onClick={() => setPreset("hour")}>
                بعد ساعة
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setPreset("tomorrow_morning")}
              >
                صباح الغد
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setPreset("tomorrow_evening")}
              >
                مساء الغد
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={!channelId || busy}
                loading={busy}
                onClick={onPublishNow}
              >
                نشر الآن
              </Button>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm" htmlFor="queue-custom-date">
              تاريخ ووقت مخصص
            </label>
            <Input
              id="queue-custom-date"
              type="datetime-local"
              value={scheduledAt}
              min={toDateTimeLocal(new Date())}
              onChange={(event) => onScheduledAtChange(event.target.value)}
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" disabled={busy} onClick={onClose}>
            إلغاء
          </Button>
          <Button
            type="button"
            disabled={!channelId || !scheduledAt || busy}
            loading={busy}
            onClick={onApply}
          >
            حفظ الجدولة
          </Button>
        </div>
      </div>
    </div>
  );
}

function toDateTimeLocal(date: Date): string {
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

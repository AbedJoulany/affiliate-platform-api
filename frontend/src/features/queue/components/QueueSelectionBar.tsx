"use client";

import { Button, Select } from "@/components/ui/primitives";
import type { QueueStatus } from "../types/api";

export function QueueSelectionBar({
  count,
  busy,
  onClear,
  onPublish,
  onReschedule,
  onDelete,
  onChangeStatus,
}: {
  count: number;
  busy: boolean;
  onClear: () => void;
  onPublish: () => void;
  onReschedule: () => void;
  onDelete: () => void;
  onChangeStatus: (status: Extract<QueueStatus, "draft" | "queued">) => void;
}) {
  if (count === 0) return null;

  return (
    <div className="sticky bottom-4 z-30 rounded-xl border border-border bg-surface/95 p-3 shadow-lg backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <p className="text-sm font-semibold">{count.toLocaleString("ar")} منشور محدد</p>
          <Button type="button" variant="ghost" className="h-8" onClick={onClear}>
            مسح التحديد
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} loading={busy} onClick={onPublish}>
            نشر المحدد
          </Button>
          <Button variant="secondary" disabled={busy} onClick={onReschedule}>
            إعادة جدولة المحدد
          </Button>
          <Button variant="outline" disabled={busy} onClick={onDelete}>
            حذف المحدد
          </Button>
          <Select
            className="w-auto"
            defaultValue=""
            disabled={busy}
            aria-label="تغيير حالة المنشورات المحددة"
            onChange={(event) => {
              const status = event.target.value as "draft" | "queued" | "";
              if (!status) return;
              onChangeStatus(status);
              event.target.value = "";
            }}
          >
            <option value="">تغيير الحالة…</option>
            <option value="draft">مسودة</option>
            <option value="queued">في الانتظار</option>
          </Select>
        </div>
      </div>
    </div>
  );
}

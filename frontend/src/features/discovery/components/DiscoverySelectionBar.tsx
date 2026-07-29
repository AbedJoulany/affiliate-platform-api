"use client";

import { Button } from "@/components/ui/primitives";

export function DiscoverySelectionBar({
  count,
  canImport,
  busy,
  onClear,
  onImport,
  onGenerateAi,
  onAddToQueue,
  onExport,
}: {
  count: number;
  canImport: boolean;
  busy: boolean;
  onClear: () => void;
  onImport: () => void;
  onGenerateAi: () => void;
  onAddToQueue: () => void;
  onExport: () => void;
}) {
  if (count === 0) return null;

  return (
    <div className="sticky bottom-4 z-30 w-full rounded-xl border border-border bg-surface/95 p-3 shadow-lg backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium">{count.toLocaleString("ar")} محدد</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={busy} onClick={onClear}>
            مسح التحديد
          </Button>
          <Button variant="outline" disabled={busy} onClick={onExport}>
            تصدير
          </Button>
          <Button variant="secondary" disabled={busy} loading={busy} onClick={onAddToQueue}>
            إضافة إلى القائمة
          </Button>
          <Button variant="secondary" disabled={busy} loading={busy} onClick={onGenerateAi}>
            إنشاء AI
          </Button>
          <Button disabled={!canImport || busy} loading={busy} onClick={onImport}>
            استيراد المحدد
          </Button>
        </div>
      </div>
      {/* Extension: future batch ops (persist candidates, assign scoring profile, schedule) */}
    </div>
  );
}

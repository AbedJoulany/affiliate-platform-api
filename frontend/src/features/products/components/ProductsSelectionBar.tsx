"use client";

import { Button, Select } from "@/components/ui/primitives";
import type { ProductStatus } from "../types/api";

export function ProductsSelectionBar({
  count,
  busy,
  canManage,
  onClear,
  onDelete,
  onChangeStatus,
  onSendToAi,
  onMoveToQueue,
  onExport,
}: {
  count: number;
  busy: boolean;
  canManage: boolean;
  onClear: () => void;
  onDelete: () => void;
  onChangeStatus: (status: ProductStatus) => void;
  onSendToAi: () => void;
  onMoveToQueue: () => void;
  onExport: () => void;
}) {
  if (count === 0) return null;

  return (
    <div className="sticky bottom-4 z-30 rounded-xl border border-border bg-surface/95 p-3 shadow-lg backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <p className="text-sm font-semibold">{count.toLocaleString("ar")} منتج محدد</p>
          <Button type="button" variant="ghost" className="h-8" onClick={onClear}>
            مسح التحديد
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={!canManage || busy}
            onClick={onDelete}
          >
            حذف المحدد
          </Button>
          <Select
            className="w-auto"
            defaultValue=""
            disabled={!canManage || busy}
            aria-label="تغيير حالة المنتجات المحددة"
            onChange={(event) => {
              if (!event.target.value) return;
              onChangeStatus(event.target.value as ProductStatus);
              event.target.value = "";
            }}
          >
            <option value="">تغيير الحالة…</option>
            <option value="draft">مسودة</option>
            <option value="active">نشط</option>
            <option value="inactive">غير نشط</option>
            <option value="archived">مؤرشف</option>
          </Select>
          <Button
            type="button"
            variant="secondary"
            disabled={count !== 1 || busy}
            title={count !== 1 ? "اختر منتجًا واحدًا لإرساله إلى جلسة AI" : undefined}
            onClick={onSendToAi}
          >
            إرسال إلى AI Studio
          </Button>
          <Button
            type="button"
            variant="secondary"
            loading={busy}
            disabled={busy}
            onClick={onMoveToQueue}
          >
            نقل إلى القائمة
          </Button>
          <Button type="button" variant="outline" disabled={busy} onClick={onExport}>
            تصدير
          </Button>
        </div>
      </div>
    </div>
  );
}

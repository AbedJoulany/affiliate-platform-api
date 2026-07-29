"use client";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";

export function DeleteProductsDialog({
  count,
  open,
  busy,
  onCancel,
  onConfirm,
}: {
  count: number;
  open: boolean;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <ConfirmDialog
      open={open}
      title={`حذف ${count === 1 ? "المنتج" : `${count.toLocaleString("ar")} منتجات`}؟`}
      message="سيُحذف المنتج من المخزون نهائيًا. لا يمكن التراجع عن هذا الإجراء."
      confirmLabel="حذف"
      destructive
      busy={busy}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />
  );
}

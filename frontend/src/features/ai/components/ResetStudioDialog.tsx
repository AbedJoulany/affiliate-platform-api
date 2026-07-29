"use client";

import { Button } from "@/components/ui/primitives";

export function ResetStudioDialog({
  open,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        className="w-full max-w-md rounded-xl border border-border bg-surface p-5 shadow-xl"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="reset-studio-title"
        aria-describedby="reset-studio-desc"
      >
        <h2 id="reset-studio-title" className="text-lg font-semibold">
          Discard current content?
        </h2>
        <p id="reset-studio-desc" className="mt-2 text-sm text-muted-foreground">
          This will remove the generated content and all current selections. This action cannot be
          undone.
        </p>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="outline"
            className="border-amber-500/40 text-amber-800 hover:bg-amber-500/10 dark:text-amber-300"
            onClick={onConfirm}
          >
            Reset
          </Button>
        </div>
      </div>
    </div>
  );
}

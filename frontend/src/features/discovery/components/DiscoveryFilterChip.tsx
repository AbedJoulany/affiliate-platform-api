"use client";

import { useRef, useState, type ReactNode } from "react";
import { Popover } from "@/components/ui/primitives";

export function DiscoveryFilterChip({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);

  return (
    <>
      <button
        ref={anchorRef}
        type="button"
        className="min-w-[7.5rem] rounded-md border border-transparent px-2.5 py-1.5 text-start transition hover:border-border hover:bg-background"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className="block text-[11px] text-muted-foreground">{label}</span>
        <span className="mt-0.5 block truncate text-sm font-semibold">{value}</span>
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchorRef}>
        <div className="space-y-3">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          {children}
          <button
            type="button"
            className="text-xs text-primary underline"
            onClick={() => setOpen(false)}
          >
            تم
          </button>
        </div>
      </Popover>
    </>
  );
}

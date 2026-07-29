"use client";

import {
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import {
  CalendarClock,
  ExternalLink,
  Eye,
  MoreHorizontal,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Button, Popover } from "@/components/ui/primitives";

export function QueueActionsMenu({
  originalUrl,
  canOpenAi,
  onView,
  onReschedule,
  onOpenAi,
  onDelete,
  extensionActions,
}: {
  originalUrl?: string | null;
  canOpenAi: boolean;
  onView: () => void;
  onReschedule: () => void;
  onOpenAi: () => void;
  onDelete: () => void;
  /** Reserved for Retry Publish and future operation plugins. */
  extensionActions?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);
  const run = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <>
      <div ref={anchorRef} className="inline-flex">
        <Button
          type="button"
          variant="ghost"
          className="h-8 px-2"
          aria-label="المزيد من إجراءات النشر"
          onClick={(event) => {
            event.stopPropagation();
            setOpen((previous) => !previous);
          }}
        >
          <MoreHorizontal className="size-4" />
        </Button>
      </div>
      <Popover
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={anchorRef}
        align="end"
        className="w-56 p-1"
      >
        <MenuItem icon={<Eye />} onClick={() => run(onView)}>
          عرض التفاصيل
        </MenuItem>
        <MenuItem icon={<CalendarClock />} onClick={() => run(onReschedule)}>
          إعادة الجدولة
        </MenuItem>
        <MenuItem icon={<Sparkles />} disabled={!canOpenAi} onClick={() => run(onOpenAi)}>
          فتح في AI Studio
        </MenuItem>
        {originalUrl ? (
          <a
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted [&_svg]:size-4"
            href={originalUrl}
            target="_blank"
            rel="noreferrer"
            onClick={() => setOpen(false)}
          >
            <ExternalLink />
            فتح المنتج الأصلي
          </a>
        ) : null}
        {extensionActions}
        <div className="my-1 border-t border-border" />
        <MenuItem icon={<Trash2 />} danger onClick={() => run(onDelete)}>
          حذف
        </MenuItem>
      </Popover>
    </>
  );
}

function MenuItem({
  icon,
  danger,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: ReactNode;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-start text-sm hover:bg-muted disabled:opacity-45 [&_svg]:size-4 ${
        danger ? "text-destructive" : ""
      }`}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}

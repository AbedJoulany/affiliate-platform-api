import * as React from "react";
import { LoaderCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  loading?: boolean;
};

export function Button({
  className,
  variant = "primary",
  loading,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const variants = {
    primary: "bg-primary text-primary-foreground hover:opacity-90",
    secondary: "bg-secondary text-secondary-foreground hover:opacity-80",
    outline: "border border-border bg-surface hover:bg-muted",
    ghost: "hover:bg-muted",
    danger: "bg-destructive text-white hover:opacity-90",
  };
  return (
    <button
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium outline-none transition focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-primary disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary",
      className,
    )}
    {...props}
  />
));
Select.displayName = "Select";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "min-h-32 w-full resize-y rounded-md border border-border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-primary",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-border bg-surface p-5", className)} {...props} />;
}

export function Badge({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warning" | "error" | "info";
}) {
  const tones = {
    neutral: "bg-muted text-muted-foreground",
    success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
    warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    error: "bg-red-500/15 text-red-700 dark:text-red-300",
    info: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
  };
  return (
    <span
      className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-medium", tones[tone], className)}
      {...props}
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} aria-hidden />;
}

export function Chip({
  active = false,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-medium transition",
        active
          ? "border-primary bg-primary/15 text-foreground"
          : "border-border bg-surface text-muted-foreground hover:bg-muted",
        className,
      )}
      aria-pressed={active}
      {...props}
    />
  );
}

export function Collapsible({
  open,
  title,
  children,
  onToggle,
  className,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onToggle: () => void;
  className?: string;
}) {
  return (
    <div className={cn("rounded-md border border-border", className)}>
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium hover:bg-muted/50"
        onClick={onToggle}
        aria-expanded={open}
      >
        <span>{title}</span>
        <span className="text-muted-foreground" aria-hidden>
          {open ? "−" : "+"}
        </span>
      </button>
      {open ? <div className="border-t border-border p-3">{children}</div> : null}
    </div>
  );
}

type DrawerProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  side?: "start" | "end";
  className?: string;
  "aria-label"?: string;
};

export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
  side = "end",
  className,
  "aria-label": ariaLabel,
}: DrawerProps) {
  React.useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const sideClasses =
    side === "start"
      ? "start-0 border-e sm:start-0 sm:end-auto sm:border-e sm:border-s-0"
      : "start-0 border-e sm:start-auto sm:end-0 sm:border-e-0 sm:border-s";

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={cn(
          "fixed inset-y-0 z-50 flex w-full max-w-md flex-col bg-surface shadow-lg",
          sideClasses,
          className,
        )}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel ?? title}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 className="font-semibold">{title}</h2>
          <Button variant="ghost" className="px-2" aria-label="إغلاق" onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
        {footer ? <div className="border-t border-border p-4">{footer}</div> : null}
      </aside>
    </>
  );
}

type PopoverProps = {
  open: boolean;
  onClose: () => void;
  anchorRef: React.RefObject<HTMLElement | null>;
  children: React.ReactNode;
  className?: string;
  align?: "start" | "end";
};

export function Popover({
  open,
  onClose,
  anchorRef,
  children,
  className,
  align = "start",
}: PopoverProps) {
  const panelRef = React.useRef<HTMLDivElement>(null);
  const [coords, setCoords] = React.useState({ top: 0, left: 0 });

  React.useLayoutEffect(() => {
    if (!open || !anchorRef.current) return;
    const rect = anchorRef.current.getBoundingClientRect();
    const panelWidth = panelRef.current?.offsetWidth ?? 280;
    const panelHeight = panelRef.current?.offsetHeight ?? 200;
    const gap = 8;
    let left = align === "end" ? rect.right - panelWidth : rect.left;
    let top = rect.bottom + gap;
    left = Math.min(Math.max(8, left), window.innerWidth - panelWidth - 8);
    if (top + panelHeight > window.innerHeight - 8) {
      top = Math.max(8, rect.top - panelHeight - gap);
    }
    setCoords({ top, left });
  }, [open, anchorRef, align]);

  React.useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (panelRef.current?.contains(target)) return;
      if (anchorRef.current?.contains(target)) return;
      onClose();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose, anchorRef]);

  if (!open) return null;

  return (
    <div
      ref={panelRef}
      className={cn(
        "fixed z-50 max-h-[min(70vh,420px)] w-[min(92vw,320px)] overflow-y-auto rounded-lg border border-border bg-surface p-3 shadow-lg",
        className,
      )}
      style={{ top: coords.top, left: coords.left }}
      role="dialog"
    >
      {children}
    </div>
  );
}

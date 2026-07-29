"use client";

import { useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import {
  Archive,
  CopyPlus,
  ExternalLink,
  Eye,
  MoreHorizontal,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Button, Popover } from "@/components/ui/primitives";
import type { Product } from "../types/api";

export function ProductActionsMenu({
  product,
  canDelete,
  onPreview,
  onGenerate,
  onDelete,
}: {
  product: Product;
  canDelete: boolean;
  onPreview: () => void;
  onGenerate: () => void;
  onDelete: () => void;
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
          aria-label={`إجراءات ${product.title}`}
          aria-expanded={open}
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
        <MenuButton icon={<Eye />} onClick={() => run(onPreview)}>
          عرض التفاصيل
        </MenuButton>
        <MenuButton icon={<Sparkles />} onClick={() => run(onGenerate)}>
          إنشاء محتوى
        </MenuButton>
        <a
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
          href={product.affiliate_url ?? product.product_url}
          target="_blank"
          rel="noreferrer"
          onClick={() => setOpen(false)}
        >
          <ExternalLink className="size-4" />
          فتح المنتج الأصلي
        </a>
        <MenuButton icon={<CopyPlus />} disabled>
          تكرار المنتج — قريبًا
        </MenuButton>
        <MenuButton icon={<Archive />} disabled>
          أرشفة المنتج — قريبًا
        </MenuButton>
        <div className="my-1 border-t border-border" />
        <MenuButton
          icon={<Trash2 />}
          danger
          disabled={!canDelete}
          onClick={() => run(onDelete)}
        >
          حذف المنتج
        </MenuButton>
      </Popover>
    </>
  );
}

function MenuButton({
  icon,
  danger,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: ReactNode;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      className={[
        "flex w-full items-center gap-2 rounded-md px-3 py-2 text-start text-sm transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45 [&_svg]:size-4",
        danger ? "text-destructive" : "",
        className ?? "",
      ].join(" ")}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}

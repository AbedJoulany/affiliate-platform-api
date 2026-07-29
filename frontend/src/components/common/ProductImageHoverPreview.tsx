"use client";

import Image from "next/image";
import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal } from "react-dom";
import { formatMoney } from "@/lib/utils";

export type ProductHoverPreviewPayload = {
  src: string;
  title: string;
  price: number;
  currency: string;
  discount: number;
  x: number;
  y: number;
};

const PREVIEW_WIDTH = 260;
const PREVIEW_HEIGHT = 320;

export function ProductImageHoverPreview({
  payload,
}: {
  payload: ProductHoverPreviewPayload | null;
}) {
  const [mounted, setMounted] = useState(false);
  const [canHover, setCanHover] = useState(false);

  useEffect(() => {
    setMounted(true);
    setCanHover(window.matchMedia("(hover: hover) and (pointer: fine)").matches);
  }, []);

  if (!mounted || !canHover || !payload) return null;

  let left = payload.x + 16;
  let top = payload.y + 16;
  if (left + PREVIEW_WIDTH > window.innerWidth - 8) {
    left = payload.x - PREVIEW_WIDTH - 16;
  }
  if (top + PREVIEW_HEIGHT > window.innerHeight - 8) {
    top = window.innerHeight - PREVIEW_HEIGHT - 8;
  }

  return createPortal(
    <div
      className="pointer-events-none fixed z-[60] w-[260px] rounded-lg border border-border bg-surface p-2 shadow-xl transition duration-150"
      style={{ left: Math.max(8, left), top: Math.max(8, top) }}
      aria-hidden
    >
      <div className="relative aspect-square overflow-hidden rounded-md bg-muted">
        <Image src={payload.src} alt="" fill className="object-cover" sizes="260px" />
      </div>
      <p className="mt-2 line-clamp-2 text-sm font-semibold leading-5">{payload.title}</p>
      <div className="mt-1.5 flex items-center justify-between gap-2 text-sm">
        <span className="font-semibold tabular-nums">
          {formatMoney(payload.price, payload.currency)}
        </span>
        {payload.discount > 0 ? (
          <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300">
            خصم {payload.discount}%
          </span>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}

export function useProductImageHover() {
  const [payload, setPayload] = useState<ProductHoverPreviewPayload | null>(null);
  const animationFrame = useRef<number | null>(null);

  const show = (
    product: Omit<ProductHoverPreviewPayload, "x" | "y">,
    event: ReactPointerEvent,
  ) => {
    setPayload({ ...product, x: event.clientX, y: event.clientY });
  };

  const move = (event: ReactPointerEvent) => {
    if (animationFrame.current != null) cancelAnimationFrame(animationFrame.current);
    const { clientX, clientY } = event;
    animationFrame.current = requestAnimationFrame(() => {
      setPayload((previous) =>
        previous ? { ...previous, x: clientX, y: clientY } : previous,
      );
      animationFrame.current = null;
    });
  };

  const hide = () => {
    if (animationFrame.current != null) cancelAnimationFrame(animationFrame.current);
    setPayload(null);
  };

  return { payload, show, move, hide };
}

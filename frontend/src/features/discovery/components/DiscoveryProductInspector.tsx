"use client";

import Image from "next/image";
import { X } from "lucide-react";
import { Badge, Button } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/utils";
import { getScoreBreakdown } from "../lib/score-explanation";
import type { DiscoveryProduct } from "../types/api";
import { DiscoveryScoreBreakdown } from "./DiscoveryScoreBreakdown";

export function DiscoveryProductInspector({
  product,
  open,
  canImport,
  importing,
  onClose,
  onImport,
  onGenerateAi,
  onAddToQueue,
  onScoreFocus,
}: {
  product: DiscoveryProduct | null;
  open: boolean;
  canImport: boolean;
  importing: boolean;
  onClose: () => void;
  onImport: (product: DiscoveryProduct) => void;
  onGenerateAi: (product: DiscoveryProduct) => void;
  onAddToQueue: (product: DiscoveryProduct) => void;
  onScoreFocus?: () => void;
}) {
  if (!open || !product) return null;
  const breakdown = getScoreBreakdown(product);
  const shipping = product.shipping_info;
  const freeShipping = shipping?.free_shipping === true;
  const images = product.gallery_images.length > 0 ? product.gallery_images : [product.image_url];

  return (
    <aside
      className="fixed inset-y-0 start-0 z-40 flex w-full max-w-md flex-col border-e border-border bg-surface shadow-lg sm:start-auto sm:end-0 sm:border-e-0 sm:border-s"
      role="dialog"
      aria-modal="true"
      aria-label="معاينة المنتج"
    >
      <div className="flex items-center justify-between border-b border-border p-4">
        <h2 className="font-semibold">معاينة المنتج</h2>
        <Button variant="ghost" className="px-2" aria-label="إغلاق" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        <div className="relative aspect-[16/10] overflow-hidden rounded-md bg-muted">
          <Image src={product.image_url} alt={product.title} fill className="object-cover" sizes="400px" />
        </div>
        {images.length > 1 && (
          <div className="flex gap-2 overflow-x-auto">
            {images.slice(0, 6).map((src) => (
              <div key={src} className="relative size-14 shrink-0 overflow-hidden rounded-md bg-muted">
                <Image src={src} alt="" fill className="object-cover" sizes="56px" />
              </div>
            ))}
          </div>
        )}

        <div>
          <h3 className="text-base font-semibold leading-7">{product.title}</h3>
          <p className="mt-2 text-2xl font-semibold">{formatMoney(product.price, product.currency)}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={onScoreFocus}>
              <Badge tone="info">نتيجة {product.score.toFixed(2)}</Badge>
            </button>
            <Badge>تقييم {product.rating.toFixed(1)}</Badge>
            <Badge>طلبات {product.sales.toLocaleString("ar")}</Badge>
            <Badge>خصم {product.discount}%</Badge>
            {product.commission_rate != null && (
              <Badge tone="success">عمولة {product.commission_rate}%</Badge>
            )}
          </div>
        </div>

        {product.description && (
          <section>
            <h4 className="mb-2 text-sm font-semibold">التفاصيل</h4>
            <p className="text-sm leading-7 text-muted-foreground">{product.description}</p>
          </section>
        )}

        <section className="rounded-md border border-border p-3">
          <DiscoveryScoreBreakdown breakdown={breakdown} />
        </section>

        <section className="space-y-2 text-sm">
          <h4 className="font-semibold">المتجر والشحن</h4>
          <p>المتجر: {product.store_name ?? "—"}</p>
          <p>الفئة: {product.category ?? "—"}</p>
          <p>الشحن المجاني: {freeShipping ? "نعم" : "غير مؤكد"}</p>
        </section>

        <section className="space-y-2 text-sm">
          <h4 className="font-semibold">بيانات الانتساب</h4>
          <p className="break-all" dir="ltr">
            ID: {product.aliexpress_product_id}
          </p>
          <a className="block break-all text-primary underline" href={product.product_url} target="_blank" rel="noreferrer" dir="ltr">
            {product.product_url}
          </a>
          {product.affiliate_url && (
            <a className="block break-all text-primary underline" href={product.affiliate_url} target="_blank" rel="noreferrer" dir="ltr">
              {product.affiliate_url}
            </a>
          )}
        </section>
      </div>

      <div className="space-y-2 border-t border-border p-4">
        <Button className="w-full" disabled={!canImport} loading={importing} onClick={() => onImport(product)}>
          استيراد المنتج
        </Button>
        <Button className="w-full" variant="outline" onClick={() => onGenerateAi(product)}>
          إنشاء محتوى AI
        </Button>
        <Button className="w-full" variant="secondary" onClick={() => onAddToQueue(product)}>
          إضافة إلى قائمة النشر
        </Button>
      </div>
    </aside>
  );
}

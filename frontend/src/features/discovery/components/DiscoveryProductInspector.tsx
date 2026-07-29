"use client";

import Image from "next/image";
import { Badge, Button, Drawer } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/utils";
import {
  estimateCommissionValue,
  getScoreBreakdown,
  getScoreQuality,
} from "../lib/score-explanation";
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
}: {
  product: DiscoveryProduct | null;
  open: boolean;
  canImport: boolean;
  importing: boolean;
  onClose: () => void;
  onImport: (product: DiscoveryProduct) => void;
  onGenerateAi: (product: DiscoveryProduct) => void;
  onAddToQueue: (product: DiscoveryProduct) => void;
}) {
  if (!product) {
    return (
      <Drawer open={open} onClose={onClose} title="معاينة المنتج" aria-label="معاينة المنتج">
        <p className="text-sm text-muted-foreground">لا يوجد منتج محدد.</p>
      </Drawer>
    );
  }

  const breakdown = getScoreBreakdown(product);
  const quality = getScoreQuality(product.score);
  const shipping = product.shipping_info;
  const freeShipping = shipping?.free_shipping === true;
  const images = product.gallery_images.length > 0 ? product.gallery_images : [product.image_url];
  const commissionValue = estimateCommissionValue(product.price, product.commission_rate);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="معاينة المنتج"
      aria-label="معاينة المنتج"
      footer={
        <div className="space-y-2">
          <Button
            className="w-full"
            disabled={!canImport}
            loading={importing}
            onClick={() => onImport(product)}
          >
            استيراد المنتج
          </Button>
          <Button className="w-full" variant="outline" onClick={() => onGenerateAi(product)}>
            إنشاء محتوى AI
          </Button>
          <Button className="w-full" variant="secondary" onClick={() => onAddToQueue(product)}>
            إضافة إلى قائمة النشر
          </Button>
          <Button
            className="w-full"
            variant="ghost"
            type="button"
            onClick={() => window.open(product.product_url, "_blank", "noopener,noreferrer")}
          >
            فتح على AliExpress
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
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
          <p className="mt-2 text-2xl font-semibold">
            {formatMoney(product.price, product.currency)}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone={quality.tone}>
              AI {Math.round(product.score)} · {quality.label}
            </Badge>
            <Badge>تقييم {product.rating.toFixed(1)}</Badge>
            <Badge>طلبات {product.sales.toLocaleString("ar")}</Badge>
            <Badge>خصم {product.discount}%</Badge>
            {product.commission_rate != null && (
              <Badge tone="success">
                عمولة {product.commission_rate}%
                {commissionValue != null
                  ? ` · ${formatMoney(commissionValue, product.currency)}`
                  : ""}
              </Badge>
            )}
          </div>
        </div>

        {product.description && (
          <section>
            <h4 className="mb-2 text-sm font-semibold">الوصف</h4>
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
          {product.affiliate_url ? (
            <a
              className="block break-all text-primary underline"
              href={product.affiliate_url}
              target="_blank"
              rel="noreferrer"
              dir="ltr"
            >
              {product.affiliate_url}
            </a>
          ) : (
            <p className="text-muted-foreground">لا يوجد رابط انتساب بعد</p>
          )}
          <a
            className="block break-all text-primary underline"
            href={product.product_url}
            target="_blank"
            rel="noreferrer"
            dir="ltr"
          >
            {product.product_url}
          </a>
        </section>
      </div>
    </Drawer>
  );
}

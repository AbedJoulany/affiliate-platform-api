"use client";

import Image from "next/image";
import { ExternalLink, Package, Sparkles } from "lucide-react";
import { ProductScoreBreakdown } from "@/components/common/ProductScoreBreakdown";
import { Badge, Button, Drawer } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/utils";
import { getProductScoreBreakdown } from "@/lib/product-score";
import type { ProductPipelineState } from "../lib/inventory";
import type { Product } from "../types/api";
import { ProductHealthBadges } from "./ProductHealthBadges";
import { ProductScoreCell } from "./ProductScoreCell";

const STATUS_LABELS = {
  draft: "مسودة",
  active: "نشط",
  inactive: "غير نشط",
  archived: "مؤرشف",
} as const;

export function ProductDetailsDrawer({
  product,
  pipelineState,
  open,
  onClose,
  onGenerateContent,
  onAddToQueue,
}: {
  product: Product | null;
  pipelineState: ProductPipelineState | null;
  open: boolean;
  onClose: () => void;
  onGenerateContent: (product: Product) => void;
  onAddToQueue: (product: Product) => void;
}) {
  const scoreBreakdown = product ? getProductScoreBreakdown(product) : null;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="تفاصيل المنتج"
      className="max-w-xl"
      footer={
        product ? (
          <div className="grid gap-2 sm:grid-cols-2">
            <Button onClick={() => onGenerateContent(product)}>
              <Sparkles className="size-4" />
              إنشاء محتوى AI
            </Button>
            <Button variant="secondary" onClick={() => onAddToQueue(product)}>
              إضافة إلى قائمة النشر
            </Button>
          </div>
        ) : null
      }
    >
      {product && pipelineState ? (
        <div className="space-y-5">
          <div className="relative aspect-square overflow-hidden rounded-lg bg-muted p-3">
            {product.image_url ? (
              <Image
                src={product.image_url}
                alt={product.title}
                fill
                className="object-contain p-3"
                sizes="560px"
              />
            ) : (
              <Package className="absolute inset-0 m-auto size-16 text-muted-foreground/50" />
            )}
          </div>

          <div>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <h3 className="max-w-md text-lg font-semibold leading-8">{product.title}</h3>
              <Badge tone={product.status === "active" ? "success" : "neutral"}>
                {STATUS_LABELS[product.status]}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {[product.category, product.store_name].filter(Boolean).join(" · ") || "غير مصنف"}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="السعر" value={formatMoney(product.price, product.currency)} />
            <Metric label="التقييم" value={`⭐ ${product.rating.toFixed(2)}`} />
            <Metric label="المبيعات" value={product.sales.toLocaleString("en")} />
            <div className="rounded-md bg-muted/40 p-3">
              <p className="text-xs text-muted-foreground">نتيجة AI</p>
              <div className="mt-1">
                <ProductScoreCell score={product.score} />
              </div>
            </div>
          </div>

          <section>
            <h4 className="mb-2 text-sm font-semibold">جاهزية المسار</h4>
            <ProductHealthBadges state={pipelineState} />
          </section>

          <section>
            <h4 className="mb-2 text-sm font-semibold">الوصف</h4>
            {product.description ? (
              <p className="whitespace-pre-line text-sm leading-7 text-muted-foreground">
                {product.description}
              </p>
            ) : (
              <div className="flex flex-wrap gap-2 rounded-md border border-dashed border-border bg-muted/20 p-3">
                <SpecBadge label="المتجر" value={product.store_name ?? "غير محدد"} />
                <SpecBadge label="الفئة" value={product.category ?? "غير مصنف"} />
                <SpecBadge
                  label="SKU"
                  value={product.aliexpress_product_id ?? product.id}
                />
                <SpecBadge
                  label="العمولة"
                  value={
                    product.commission_rate != null
                      ? `${product.commission_rate}%`
                      : "غير متاحة"
                  }
                />
              </div>
            )}
          </section>

          {scoreBreakdown ? (
            <section className="rounded-md border border-border p-3">
              <ProductScoreBreakdown breakdown={scoreBreakdown} />
            </section>
          ) : null}

          <dl className="space-y-2 rounded-md border border-border p-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">SKU / AliExpress ID</dt>
              <dd className="break-all text-end" dir="ltr">
                {product.aliexpress_product_id ?? product.id}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">الخصم</dt>
              <dd>{product.discount}%</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">العمولة</dt>
              <dd>{product.commission_rate != null ? `${product.commission_rate}%` : "—"}</dd>
            </div>
          </dl>

          <a
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            href={product.affiliate_url ?? product.product_url}
            target="_blank"
            rel="noreferrer"
          >
            فتح المنتج الأصلي
            <ExternalLink className="size-4" />
          </a>
        </div>
      ) : null}
    </Drawer>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function SpecBadge({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="max-w-56 truncate font-medium" dir={label === "SKU" ? "ltr" : undefined}>
        {value}
      </span>
    </span>
  );
}

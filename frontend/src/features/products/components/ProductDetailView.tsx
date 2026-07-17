"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Button, Card } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/utils";
import { useProduct } from "../hooks/useProducts";

export function ProductDetailView({ id }: { id: string }) {
  const product = useProduct(id);
  if (product.isPending) return <PageContainer><LoadingState rows={6} /></PageContainer>;
  if (product.isError) return <PageContainer><ErrorState message="تعذر تحميل المنتج." onRetry={() => void product.refetch()} /></PageContainer>;
  return (
    <PageContainer>
      <Link className="mb-4 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground" href="/products">
        <ArrowRight className="size-4" /> المنتجات
      </Link>
      <PageHeader title={product.data.title} description={`معرّف المنتج: ${product.data.aliexpress_product_id ?? product.data.id}`} actions={<Link href={`/ai?product=${product.data.id}`}><Button>إنشاء محتوى</Button></Link>} />
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <Card className="overflow-hidden p-0">
          <div className="relative aspect-square bg-muted">
            <Image src={product.data.image_url} alt={product.data.title} fill className="object-cover" sizes="360px" />
          </div>
        </Card>
        <div className="space-y-5">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><p className="text-sm text-muted-foreground">السعر</p><p className="mt-1 text-3xl font-semibold">{formatMoney(product.data.price, product.data.currency)}</p></div>
              <Badge tone={product.data.status === "active" ? "success" : "neutral"}>{product.data.status}</Badge>
            </div>
            <dl className="mt-6 grid gap-4 border-t border-border pt-5 sm:grid-cols-3">
              <div><dt className="text-sm text-muted-foreground">التقييم</dt><dd className="mt-1 font-medium">{product.data.rating} / 5</dd></div>
              <div><dt className="text-sm text-muted-foreground">المبيعات</dt><dd className="mt-1 font-medium">{product.data.sales}</dd></div>
              <div><dt className="text-sm text-muted-foreground">النتيجة</dt><dd className="mt-1 font-medium">{product.data.score}</dd></div>
            </dl>
          </Card>
          <Card>
            <h2 className="font-semibold">تفاصيل المنتج</h2>
            <p className="mt-3 whitespace-pre-line text-sm leading-7 text-muted-foreground">{product.data.description || "لا يتوفر وصف."}</p>
            <a className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline" href={product.data.affiliate_url ?? product.data.product_url} target="_blank" rel="noreferrer">
              فتح المنتج <ExternalLink className="size-4" />
            </a>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}

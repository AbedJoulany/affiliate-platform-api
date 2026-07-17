"use client";

import { useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Button, Card, Input, Select } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/utils";
import { useProducts } from "../hooks/useProducts";
import type { ProductStatus } from "../types/api";

const PAGE_SIZE = 20;

export function ProductsView() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ProductStatus | "">("");
  const [page, setPage] = useState(0);
  const products = useProducts({
    title: search || undefined,
    status: status || undefined,
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  });

  return (
    <PageContainer>
      <PageHeader title="المنتجات" description="راجع المنتجات المستوردة وجهّزها للنشر." />
      <Card className="mb-5 grid gap-3 sm:grid-cols-[1fr_200px]">
        <label className="relative">
          <span className="sr-only">البحث في المنتجات</span>
          <Search className="absolute right-3 top-3 size-4 text-muted-foreground" aria-hidden />
          <Input className="pr-9" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="ابحث بالعنوان..." />
        </label>
        <Select aria-label="تصفية حسب الحالة" value={status} onChange={(event) => { setStatus(event.target.value as ProductStatus | ""); setPage(0); }}>
          <option value="">كل الحالات</option>
          <option value="draft">مسودة</option>
          <option value="active">نشط</option>
          <option value="inactive">غير نشط</option>
          <option value="archived">مؤرشف</option>
        </Select>
      </Card>
      {products.isPending ? (
        <LoadingState />
      ) : products.isError ? (
        <ErrorState onRetry={() => void products.refetch()} />
      ) : products.data.items.length === 0 ? (
        <EmptyState title="لا توجد منتجات" description="ابدأ من صفحة الاكتشاف لاستيراد أول منتج." action={<Link href="/discovery"><Button>بدء الاكتشاف</Button></Link>} />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border bg-surface">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-muted/60 text-right text-muted-foreground">
                <tr><th className="p-3">المنتج</th><th className="p-3">السعر</th><th className="p-3">التقييم</th><th className="p-3">النتيجة</th><th className="p-3">الحالة</th><th className="p-3">الإجراء</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {products.data.items.map((product) => (
                  <tr key={product.id}>
                    <td className="max-w-sm p-3 font-medium">{product.title}</td>
                    <td className="p-3">{formatMoney(product.price, product.currency)}</td>
                    <td className="p-3">{product.rating} / 5</td>
                    <td className="p-3">{product.score}</td>
                    <td className="p-3"><Badge tone={product.status === "active" ? "success" : "neutral"}>{product.status}</Badge></td>
                    <td className="p-3"><Link className="font-medium text-primary hover:underline" href={`/products/${product.id}`}>عرض التفاصيل</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{products.data.total} منتج</p>
            <div className="flex gap-2">
              <Button variant="outline" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>السابق</Button>
              <Button variant="outline" disabled={(page + 1) * PAGE_SIZE >= products.data.total} onClick={() => setPage((value) => value + 1)}>التالي</Button>
            </div>
          </div>
        </>
      )}
    </PageContainer>
  );
}

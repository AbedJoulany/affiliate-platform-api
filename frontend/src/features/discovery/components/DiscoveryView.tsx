"use client";

import { useState } from "react";
import Image from "next/image";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Button, Card, Input, Select } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/utils";
import { useCategories } from "@/features/categories/hooks/useCategories";
import { useCurrentUser } from "@/features/auth/hooks/useAuth";
import { useDiscovery, useImportProduct } from "../hooks/useDiscovery";
import type { DiscoveryParams } from "../types/api";

const schema = z.object({
  mode: z.enum(["general", "hot", "deals", "trending", "category"]),
  keywords: z.string().max(255).optional(),
  category_id: z.string().optional(),
  min_rating: z.coerce.number().min(0).max(5).optional(),
  min_discount: z.coerce.number().min(0).max(100).optional(),
}).refine((values) => values.mode !== "category" || Boolean(values.category_id), {
  message: "اختر فئة",
  path: ["category_id"],
});
type Values = z.infer<typeof schema>;
type InputValues = z.input<typeof schema>;

export function DiscoveryView() {
  const [params, setParams] = useState<DiscoveryParams>({});
  const [started, setStarted] = useState(false);
  const currentUser = useCurrentUser();
  const categories = useCategories();
  const discovery = useDiscovery(params, started);
  const importer = useImportProduct();
  const { register, handleSubmit, watch, formState: { errors } } = useForm<InputValues, unknown, Values>({
    resolver: zodResolver(schema),
    defaultValues: { mode: "hot" },
  });
  const mode = watch("mode");
  const canImport = currentUser.data?.role === "admin";

  return (
    <PageContainer>
      <PageHeader title="اكتشاف المنتجات" description="ابحث في مصادر AliExpress واستورد المنتجات المناسبة." />
      <Card className="mb-6">
        <form className="grid gap-4 md:grid-cols-2 xl:grid-cols-5" onSubmit={handleSubmit((values) => { setParams(values); setStarted(true); })}>
          <div><label className="mb-1.5 block text-sm" htmlFor="mode">المصدر</label><Select id="mode" {...register("mode")}><option value="hot">الأكثر رواجًا</option><option value="trending">الصاعدة</option><option value="deals">العروض</option><option value="general">عام</option><option value="category">فئة</option></Select></div>
          <div><label className="mb-1.5 block text-sm" htmlFor="keywords">كلمات البحث</label><Input id="keywords" {...register("keywords")} /></div>
          {mode === "category" ? (
            <div><label className="mb-1.5 block text-sm" htmlFor="category">الفئة</label><Select id="category" disabled={categories.isPending || categories.isError} aria-invalid={!!errors.category_id} {...register("category_id")}><option value="">اختر فئة</option>{categories.data?.items.map((category) => <option value={String(category.category_id)} key={category.category_id}>{category.category_name}</option>)}</Select>{errors.category_id && <p className="mt-1 text-sm text-destructive">{errors.category_id.message}</p>}</div>
          ) : <div><label className="mb-1.5 block text-sm" htmlFor="rating">أدنى تقييم</label><Input id="rating" type="number" step="0.1" {...register("min_rating")} /></div>}
          <div><label className="mb-1.5 block text-sm" htmlFor="discount">أدنى خصم %</label><Input id="discount" type="number" {...register("min_discount")} /></div>
          <Button className="self-end" type="submit" loading={discovery.isFetching}>بدء الاكتشاف</Button>
        </form>
      </Card>
      {importer.isError && <p className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">{importer.error.message}</p>}
      {importer.isSuccess && <p className="mb-4 rounded-md bg-emerald-500/10 p-3 text-sm text-emerald-700" role="status">تم استيراد المنتج بنجاح.</p>}
      {!canImport && <p className="mb-4 text-sm text-muted-foreground">استيراد المنتجات متاح لحسابات المدير فقط.</p>}
      {!started ? (
        <EmptyState title="ابدأ عملية اكتشاف" description="اختر مصدرًا وفلاتر، ثم شغّل الاكتشاف." />
      ) : discovery.isPending ? (
        <LoadingState rows={6} />
      ) : discovery.isError ? (
        <ErrorState message="تعذر تشغيل الاكتشاف." onRetry={() => void discovery.refetch()} />
      ) : discovery.data.items.length === 0 ? (
        <EmptyState title="لا توجد نتائج" description="جرّب توسيع معايير البحث." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {discovery.data.items.map((product) => (
            <Card className="overflow-hidden p-0" key={product.aliexpress_product_id}>
              <div className="relative aspect-[16/10] bg-muted"><Image src={product.image_url} alt={product.title} fill className="object-cover" sizes="(max-width: 640px) 100vw, 33vw" /></div>
              <div className="p-4">
                <h2 className="line-clamp-2 min-h-12 font-medium">{product.title}</h2>
                <div className="mt-3 flex items-center justify-between"><span className="font-semibold">{formatMoney(product.price, product.currency)}</span><Badge tone="info">نتيجة {product.score}</Badge></div>
                <Button className="mt-4 w-full" variant="outline" disabled={!canImport} loading={importer.isPending && importer.variables === product.aliexpress_product_id} onClick={() => importer.mutate(product.aliexpress_product_id)}>استيراد المنتج</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </PageContainer>
  );
}

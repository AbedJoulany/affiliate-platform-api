"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Copy, ListPlus, Sparkles } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Button, Card, Input, Select, Textarea } from "@/components/ui/primitives";
import { useCreateQueueItem } from "@/features/queue/hooks/useQueue";
import { useGenerateContent } from "../hooks/useGenerateContent";

const schema = z.object({
  sourceType: z.enum(["product", "url"]),
  source: z.string().min(1, "المصدر مطلوب"),
  provider: z.enum(["openai", "gemini"]),
});
type Values = z.infer<typeof schema>;

export function AIStudioView({
  initialProductId,
  initialUrl,
}: {
  initialProductId?: string;
  initialUrl?: string;
}) {
  const generation = useGenerateContent();
  const queue = useCreateQueueItem();
  const [content, setContent] = useState("");
  const { register, handleSubmit, watch, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      sourceType: initialProductId ? "product" : "url",
      source: initialProductId ?? initialUrl ?? "",
      provider: "openai",
    },
  });
  const sourceType = watch("sourceType");
  const submit = (values: Values) => {
    const input = values.sourceType === "product"
      ? { product_id: values.source, provider: values.provider }
      : { url: values.source, provider: values.provider };
    generation.mutate(input, { onSuccess: (data) => setContent(data.content) });
  };
  return (
    <PageContainer>
      <PageHeader title="استوديو الذكاء الاصطناعي" description="أنشئ محتوى تسويقيًا عربيًا من منتج أو رابط." />
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <Card>
          <form className="space-y-4" onSubmit={handleSubmit(submit)}>
            <div><label className="mb-1.5 block text-sm" htmlFor="sourceType">نوع المصدر</label><Select id="sourceType" {...register("sourceType")}><option value="product">منتج محفوظ</option><option value="url">رابط منتج</option></Select></div>
            <div><label className="mb-1.5 block text-sm" htmlFor="source">{sourceType === "product" ? "معرّف المنتج" : "رابط المنتج"}</label><Input id="source" dir="ltr" {...register("source")} aria-invalid={!!errors.source} />{errors.source && <p className="mt-1 text-sm text-destructive">{errors.source.message}</p>}</div>
            <div><label className="mb-1.5 block text-sm" htmlFor="provider">المزوّد</label><Select id="provider" {...register("provider")}><option value="openai">OpenAI</option><option value="gemini">Gemini</option></Select></div>
            {generation.isError && <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">{generation.error.message}</p>}
            <Button className="w-full" type="submit" loading={generation.isPending}><Sparkles className="size-4" /> إنشاء المحتوى</Button>
          </form>
        </Card>
        <Card>
          <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">المحتوى</h2><Button variant="ghost" className="px-2" disabled={!content} onClick={() => void navigator.clipboard.writeText(content)} aria-label="نسخ المحتوى"><Copy className="size-4" /></Button></div>
          <Textarea className="min-h-[420px] leading-8" value={content} onChange={(event) => setContent(event.target.value)} placeholder="سيظهر المحتوى المُنشأ هنا ويمكنك تحريره..." />
          <p className="mt-2 text-xs text-muted-foreground">{content.length} حرفًا — التعديلات محلية حتى إضافتها إلى قائمة النشر.</p>
          {queue.isError && <p className="mt-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">{queue.error.message}</p>}
          {queue.isSuccess && <p className="mt-3 rounded-md bg-emerald-500/10 p-3 text-sm text-emerald-700" role="status">تمت إضافة مسودة إلى قائمة النشر.</p>}
          <Button
            className="mt-4"
            disabled={!content.trim()}
            loading={queue.isPending}
            onClick={() => queue.mutate({
              content: content.trim(),
              status: "draft",
              product_id: generation.data?.product_id,
            })}
          >
            <ListPlus className="size-4" /> إضافة كمسودة إلى قائمة النشر
          </Button>
        </Card>
      </div>
    </PageContainer>
  );
}

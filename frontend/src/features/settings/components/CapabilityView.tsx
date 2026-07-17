"use client";

import { CheckCircle2, CircleAlert, LockKeyhole } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/common/states";
import { Badge, Card } from "@/components/ui/primitives";
import { usePlatformReadiness } from "@/features/categories/hooks/useCategories";

type Capability = "aliexpress" | "ai" | "telegram";

export function CapabilityView({
  title,
  description,
  capability,
  details,
}: {
  title: string;
  description: string;
  capability?: Capability;
  details: ReadonlyArray<[string, string]>;
}) {
  const readiness = usePlatformReadiness();
  if (capability && readiness.isPending) return <LoadingState rows={3} />;
  if (capability && readiness.isError) return <ErrorState message="واجهة الجاهزية غير متاحة بعد؛ لا يمكن عرض حالة آمنة." onRetry={() => void readiness.refetch()} />;
  const ready = capability ? readiness.data?.status === "ready" : undefined;
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-lg font-semibold">{title}</h2><p className="mt-1 text-sm text-muted-foreground">{description}</p></div>
        {capability && <Badge tone={ready ? "success" : "warning"}>{ready ? "الخدمات الأساسية جاهزة" : "الخدمات الأساسية غير جاهزة"}</Badge>}
      </div>
      <div className="mt-6 space-y-3">
        {details.map(([label, value]) => <div className="flex items-center justify-between gap-4 rounded-md bg-muted/50 p-3 text-sm" key={label}><span>{label}</span><span className="text-left text-muted-foreground">{value}</span></div>)}
      </div>
      <div className="mt-6 flex gap-3 rounded-md border border-border p-4 text-sm text-muted-foreground">
        {ready ? <CheckCircle2 className="size-5 shrink-0 text-emerald-600" /> : capability ? <CircleAlert className="size-5 shrink-0 text-amber-600" /> : <LockKeyhole className="size-5 shrink-0" />}
        <p>تعكس الشارة جاهزية قاعدة البيانات وRedis فقط، ولا تكشف حالة مفاتيح المزوّدين. هذه شاشة للقراءة فقط وتُدار الأسرار من بيئة الخادم.</p>
      </div>
    </Card>
  );
}

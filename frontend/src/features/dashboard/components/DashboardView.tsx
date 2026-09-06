"use client";

import Link from "next/link";
import { BrainCircuit, Compass, Package, Radio, Send } from "lucide-react";
import { ErrorState, LoadingState, NoActiveWorkspaceState } from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Card } from "@/components/ui/primitives";
import { useDashboard } from "../hooks/useDashboard";
import { getApiErrorMessage } from "@/services/api-client";
import { useActiveWorkspaceId } from "@/lib/workspace";

export function DashboardView() {
  const workspaceId = useActiveWorkspaceId();
  const overview = useDashboard();
  if (!workspaceId) {
    return (
      <PageContainer>
        <PageHeader title="لوحة التحكم" description="نظرة عامة على مساحة الأتمتة." />
        <NoActiveWorkspaceState />
      </PageContainer>
    );
  }
  if (overview.isPending) return <PageContainer><LoadingState rows={6} /></PageContainer>;
  if (overview.isError) {
    return (
      <PageContainer>
        <PageHeader title="لوحة التحكم" description="نظرة عامة على مساحة الأتمتة." />
        <ErrorState
          message={getApiErrorMessage(overview.error, "تعذر تحميل لوحة التحكم.")}
          onRetry={() => void overview.refetch()}
        />
      </PageContainer>
    );
  }
  const stats = [
    ["المنتجات", overview.data.products.total, Package],
    ["قائمة النشر", overview.data.queue.total, Radio],
    ["تم النشر", overview.data.queue.by_status.published, Send],
    ["القنوات النشطة", overview.data.channels.active, Radio],
  ] as const;
  return (
    <PageContainer>
      <PageHeader title="لوحة التحكم" description="نظرة عامة على مساحة الأتمتة." />
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="الإحصاءات">
        {stats.map(([label, value, Icon]) => (
          <Card key={label}>
            <Icon className="mb-4 size-5 text-primary" aria-hidden />
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 text-3xl font-semibold">{value}</p>
          </Card>
        ))}
      </section>
      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        {[
          ["استكشف منتجات", "اعثر على منتجات واعدة من AliExpress.", "/discovery", Compass],
          ["أنشئ محتوى", "حوّل منتجًا إلى محتوى تسويقي عربي.", "/ai", BrainCircuit],
          ["راجع قائمة النشر", "تابع المسودات والمنشورات المجدولة.", "/queue", Radio],
        ].map(([title, description, href, Icon]) => (
          <Link href={String(href)} key={String(href)}>
            <Card className="h-full transition hover:border-primary">
              <Icon className="mb-4 size-5 text-primary" aria-hidden />
              <h2 className="font-semibold">{String(title)}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{String(description)}</p>
            </Card>
          </Link>
        ))}
      </section>
      <section className="mt-6 grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card>
          <h2 className="font-semibold">النشاط الأخير</h2>
          {overview.data.recent_activity.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">لا يوجد نشاط حديث.</p>
          ) : (
            <ul className="mt-4 divide-y divide-border">
              {overview.data.recent_activity.map((item) => (
                <li className="flex items-center justify-between gap-4 py-3 text-sm" key={`${item.resource_type}-${item.resource_id}`}>
                  <span className="truncate">{item.title}</span>
                  <span className="text-muted-foreground">{item.status}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="font-semibold">حالة النظام</h2>
          <p className="mt-4 text-sm text-muted-foreground">قاعدة البيانات</p>
          <p className="mt-1 font-medium text-emerald-700">تعمل</p>
          <p className="mt-4 text-xs text-muted-foreground">
            آخر فحص: {new Intl.DateTimeFormat("ar", { dateStyle: "medium", timeStyle: "short" }).format(new Date(overview.data.system_status.generated_at))}
          </p>
        </Card>
      </section>
    </PageContainer>
  );
}

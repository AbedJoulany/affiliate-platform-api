"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpLeft,
  CalendarClock,
  CheckCircle2,
  CircleAlert,
  Globe2,
  Info,
  ListChecks,
  Package,
  Radio,
  Send,
  Settings2,
  TriangleAlert,
} from "lucide-react";
import { ErrorState, EmptyState, LoadingState, NoActiveWorkspaceState } from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Card } from "@/components/ui/primitives";
import { getApiErrorMessage } from "@/services/api-client";
import { useActiveWorkspaceId } from "@/lib/workspace";
import { useDashboard } from "../hooks/useDashboard";
import type { DashboardOverview } from "../types/api";

const numberFormatter = new Intl.NumberFormat("ar");

export function DashboardView() {
  const workspaceId = useActiveWorkspaceId();
  const overview = useDashboard();

  if (!workspaceId) {
    return (
      <PageContainer>
        <PageHeader title="لوحة التحكم" description="نظرة عملية على قائمة النشر والوجهات." />
        <NoActiveWorkspaceState />
      </PageContainer>
    );
  }

  if (overview.isPending) {
    return (
      <PageContainer>
        <PageHeader title="لوحة التحكم" description="نظرة عملية على قائمة النشر والوجهات." />
        <LoadingState rows={8} />
      </PageContainer>
    );
  }

  if (overview.isError) {
    return (
      <PageContainer>
        <PageHeader title="لوحة التحكم" description="نظرة عملية على قائمة النشر والوجهات." />
        <ErrorState
          message={getApiErrorMessage(overview.error, "تعذر تحميل لوحة التحكم.")}
          onRetry={() => void overview.refetch()}
        />
      </PageContainer>
    );
  }

  const data = overview.data;
  return (
    <PageContainer>
      <PageHeader
        title="لوحة التحكم"
        description="نظرة عملية على قائمة النشر والوجهات وما يحتاج إلى متابعة."
        actions={
          <div className="rounded-md border border-border bg-surface px-3 py-2 text-end text-xs">
            <p className="text-muted-foreground">مساحة العمل النشطة</p>
            <p className="mt-1 max-w-48 truncate font-mono" title={workspaceId}>
              {workspaceId}
            </p>
          </div>
        }
      />

      <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-2">
          <Info className="size-4" aria-hidden />
          التقرير حسب اليوم المحلي لمساحة العمل
        </span>
        <span data-testid="dashboard-timezone">المنطقة الزمنية: {data.reporting.timezone}</span>
        <span>
          آخر تحديث: {formatTimestamp(data.reporting.generated_at, data.reporting.timezone)}
        </span>
      </div>

      <DashboardKpis data={data} />

      <section className="mt-6 grid gap-4 lg:grid-cols-[1fr_1.5fr]" aria-label="ملخص الحالة">
        <Card>
          <SectionHeading icon={<ListChecks className="size-5" />} title="ملخص قائمة النشر" />
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Metric label="إجمالي العناصر" value={data.queue.total} />
            <Metric label="مسودات" value={data.queue.by_status.draft} />
            <Metric
              label="منشورة حاليًا"
              value={
                data.publishing.by_provider.telegram.published +
                data.publishing.by_provider.facebook.published
              }
            />
            <Metric label="غير مؤكدة" value={data.publishing.ambiguous_unresolved} tone="warning" />
          </div>
        </Card>
        <Card>
          <SectionHeading icon={<Radio className="size-5" />} title="الحالة حسب المزوّد" />
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <ProviderSummary
              label="Telegram"
              icon={<Send className="size-4" />}
              published={data.publishing.by_provider.telegram.published}
              failed={data.publishing.by_provider.telegram.failed}
            />
            <ProviderSummary
              label="Facebook"
              icon={<Globe2 className="size-4" />}
              published={data.publishing.by_provider.facebook.published}
              failed={data.publishing.by_provider.facebook.failed}
            />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            هذه الأرقام تعكس الحالة الحالية للعناصر، وليست نشاط اليوم.
          </p>
        </Card>
      </section>

      <section className="mt-6" aria-labelledby="attention-heading">
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <SectionHeading
              icon={<TriangleAlert className="size-5 text-amber-600" />}
              title="يحتاج إلى متابعتك"
              id="attention-heading"
            />
            {data.publishing.ambiguous_unresolved > 0 ? (
              <Badge tone="warning">
                {numberFormatter.format(data.publishing.ambiguous_unresolved)} غير مؤكدة
              </Badge>
            ) : null}
          </div>

          {data.attention_items.length === 0 ? (
            <EmptyState
              title="لا توجد عناصر تحتاج إلى متابعة"
              description="لا توجد حاليًا حالات فشل أو نتائج نشر غير مؤكدة ضمن مساحة العمل."
            />
          ) : (
            <ul className="mt-4 divide-y divide-border" aria-label="عناصر تحتاج إلى متابعة">
              {data.attention_items.map((item) => (
                <li key={item.queue_id} className="py-4 first:pt-1 last:pb-1">
                  <Link
                    href={`/queue?item=${encodeURIComponent(item.queue_id)}`}
                    className="group flex flex-col gap-3 rounded-md p-2 transition hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate font-medium group-hover:text-primary">{item.title}</p>
                        <Badge tone={item.issue === "ambiguous" ? "warning" : "error"}>
                          {item.issue === "ambiguous" ? "نتيجة غير مؤكدة" : "فشل النشر"}
                        </Badge>
                        <Badge tone="neutral">{providerLabel(item.provider)}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {item.issue === "ambiguous"
                          ? "قد يكون المزوّد قبل المنشور؛ راجع قائمة النشر قبل أي إعادة محاولة."
                          : item.message ?? item.error_code ?? "تعذر نشر هذا العنصر."}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatTimestamp(item.occurred_at, data.reporting.timezone)}
                        {item.error_code ? ` · ${item.error_code}` : ""}
                      </p>
                    </div>
                    <span className="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-primary">
                      فتح في قائمة النشر
                      <ArrowUpLeft className="size-4" aria-hidden />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-2" aria-label="جاهزية الوجهات">
        <ReadinessCard
          title="جاهزية Telegram"
          icon={<Send className="size-5" />}
          lines={[
            ["إجمالي القنوات", data.destination_readiness.telegram.total],
            ["القنوات النشطة", data.destination_readiness.telegram.active],
            ["صلاحيات البوت المفحوصة", data.destination_readiness.telegram.permission_granted],
          ]}
          note="يشمل العدد الأخير الحالات المؤكدة أو الجزئية من فحص صلاحيات البوت."
          href="/channels"
          linkLabel="إدارة القنوات"
        />
        <ReadinessCard
          title="جاهزية Facebook"
          icon={<Globe2 className="size-5" />}
          lines={[
            ["إجمالي الصفحات", data.destination_readiness.facebook.total],
            ["الصفحات النشطة", data.destination_readiness.facebook.active],
            ["الصفحات التي تم التحقق منها", data.destination_readiness.facebook.validated],
          ]}
          note={
            data.destination_readiness.facebook.publishing_permission_verified
              ? "صلاحية النشر موثقة من النظام."
              : "التحقق من الصفحة لا يثبت صلاحية النشر الفعلية عبر Meta."
          }
          href="/channels"
          linkLabel="إدارة الصفحات"
          warning={!data.destination_readiness.facebook.publishing_permission_verified}
        />
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <SectionHeading icon={<Radio className="size-5" />} title="النشاط الأخير" />
          {data.recent_activity.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">لا يوجد نشاط حديث.</p>
          ) : (
            <ul className="mt-4 divide-y divide-border">
              {data.recent_activity.map((item) => {
                const href =
                  item.resource_type === "queue"
                    ? `/queue?item=${encodeURIComponent(item.resource_id)}`
                    : `/products/${encodeURIComponent(item.resource_id)}`;
                return (
                  <li key={`${item.resource_type}-${item.resource_id}`}>
                    <Link
                      href={href}
                      className="flex items-center justify-between gap-4 py-3 text-sm hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      <span className="min-w-0 truncate">
                        <span className="me-2 text-xs text-muted-foreground">
                          {item.resource_type === "queue" ? "قائمة النشر" : "منتج"}
                        </span>
                        {item.title}
                      </span>
                      <span className="shrink-0 text-muted-foreground">
                        {item.status} · {formatTimestamp(item.occurred_at, data.reporting.timezone)}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
        <div className="space-y-4">
          <Card>
            <SectionHeading icon={<Package className="size-5" />} title="الكتالوج والمنتجات" />
            <p className="mt-4 text-3xl font-semibold tabular-nums">
              {numberFormatter.format(data.products.total)}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              إجمالي المنتجات في الكتالوج المشترك، وليس خاصًا بمساحة العمل.
            </p>
            <Link href="/products" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
              فتح الكتالوج <ArrowUpLeft className="size-4" aria-hidden />
            </Link>
          </Card>
          <Card>
            <SectionHeading icon={<Settings2 className="size-5" />} title="الأتمتة" />
            <p className="mt-3 font-medium">غير مهيأة</p>
            <p className="mt-1 text-sm text-muted-foreground">
              لا توجد أتمتة قيد التشغيل. سيظهر وقت آخر تشغيل بعد تفعيل هذه المرحلة.
            </p>
          </Card>
        </div>
      </section>
    </PageContainer>
  );
}

function DashboardKpis({ data }: { data: DashboardOverview }) {
  const items = [
    {
      id: "queued",
      label: "في قائمة الانتظار",
      helper: "حالة حالية",
      value: data.queue.by_status.queued,
      icon: ListChecks,
      className: "text-primary",
    },
    {
      id: "scheduled",
      label: "مجدول",
      helper: "حالة حالية",
      value: data.queue.by_status.scheduled,
      icon: CalendarClock,
      className: "text-blue-600",
    },
    {
      id: "published-today",
      label: "نُشر اليوم",
      helper: "حدث خلال اليوم المحلي",
      value: data.publishing.published_today,
      icon: CheckCircle2,
      className: "text-emerald-600",
    },
    {
      id: "failed-today",
      label: "فشل اليوم",
      helper: "محاولة فاشلة خلال اليوم المحلي",
      value: data.publishing.failed_today,
      icon: CircleAlert,
      className: "text-red-600",
    },
  ] as const;

  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="مؤشرات لوحة العمليات">
      {items.map(({ id, label, helper, value, icon: Icon, className }) => (
        <Card key={id} data-testid={`dashboard-kpi-${id}`}>
          <Icon className={`mb-4 size-5 ${className}`} aria-hidden />
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-3xl font-semibold tabular-nums">{numberFormatter.format(value)}</p>
          <p className="mt-2 text-xs text-muted-foreground">{helper}</p>
        </Card>
      ))}
    </section>
  );
}

function SectionHeading({
  icon,
  title,
  id,
}: {
  icon: React.ReactNode;
  title: string;
  id?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-primary" aria-hidden>
        {icon}
      </span>
      <h2 id={id} className="font-semibold">
        {title}
      </h2>
    </div>
  );
}

function Metric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "warning";
}) {
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${tone === "warning" ? "text-amber-700 dark:text-amber-300" : ""}`}>
        {numberFormatter.format(value)}
      </p>
    </div>
  );
}

function ProviderSummary({
  label,
  icon,
  published,
  failed,
}: {
  label: string;
  icon: React.ReactNode;
  published: number;
  failed: number;
}) {
  return (
    <div className="rounded-md border border-border p-3">
      <p className="flex items-center gap-2 text-sm font-medium">
        {icon}
        {label}
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">منشور</dt>
          <dd className="mt-1 font-semibold text-emerald-700 dark:text-emerald-300">{numberFormatter.format(published)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">فاشل</dt>
          <dd className="mt-1 font-semibold text-red-700 dark:text-red-300">{numberFormatter.format(failed)}</dd>
        </div>
      </dl>
    </div>
  );
}

function ReadinessCard({
  title,
  icon,
  lines,
  note,
  href,
  linkLabel,
  warning = false,
}: {
  title: string;
  icon: React.ReactNode;
  lines: ReadonlyArray<readonly [string, number]>;
  note: string;
  href: string;
  linkLabel: string;
  warning?: boolean;
}) {
  return (
    <Card>
      <SectionHeading icon={icon} title={title} />
      <dl className="mt-4 grid gap-3 sm:grid-cols-3">
        {lines.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums">{numberFormatter.format(value)}</dd>
          </div>
        ))}
      </dl>
      <p className={`mt-4 flex items-start gap-2 text-xs ${warning ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground"}`}>
        {warning ? <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /> : null}
        {note}
      </p>
      <Link href={href} className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
        {linkLabel} <ArrowUpLeft className="size-4" aria-hidden />
      </Link>
    </Card>
  );
}

function providerLabel(provider: "telegram" | "facebook") {
  return provider === "facebook" ? "Facebook" : "Telegram";
}

function formatTimestamp(value: string, timezone: string) {
  try {
    return new Intl.DateTimeFormat("ar", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: timezone,
    }).format(new Date(value));
  } catch {
    return new Intl.DateTimeFormat("ar", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  }
}

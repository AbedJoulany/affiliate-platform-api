"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { AlertTriangle, LockKeyhole } from "lucide-react";
import {
  ErrorState,
  LoadingState,
  NoActiveWorkspaceState,
} from "@/components/common/states";
import { ToastOverlay } from "@/components/common/ToastOverlay";
import { Badge, Button, Card, Input, Select } from "@/components/ui/primitives";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { useActiveWorkspaceId } from "@/lib/workspace";
import { getApiErrorMessage, type ApiError } from "@/services/api-client";
import { useWorkspaceSettings } from "@/features/settings/hooks/useWorkspaceSettings";
import {
  useChannels,
  useFacebookPages,
} from "@/features/channels/hooks/useChannels";
import type { Channel, FacebookPage } from "@/features/channels/types/api";
import {
  useAutomationPolicy,
  usePatchAutomationPolicy,
} from "../hooks/useAutomationPolicy";
import type {
  AutomationDestination,
  AutomationPolicy,
} from "../types/api";
import {
  automationFormSchema,
  type AutomationFormValues,
} from "../lib/schemas";
import {
  buildAutomationPatch,
  toAutomationFormValues,
} from "../lib/form-mappers";

const fieldClass = "grid gap-1.5";

export function AutomationSettingsView() {
  const workspaceId = useActiveWorkspaceId();
  const policy = useAutomationPolicy();
  const settings = useWorkspaceSettings();
  const channels = useChannels();
  const pages = useFacebookPages();

  if (!workspaceId) {
    return (
      <PageContainer>
        <PageHeader title="إعدادات الأتمتة" description="احفظ سياسة الأتمتة لمساحة العمل الحالية." />
        <NoActiveWorkspaceState />
      </PageContainer>
    );
  }
  if (policy.isPending || settings.isPending) return <PageContainer><LoadingState rows={8} /></PageContainer>;
  if (policy.isError) {
    return (
      <PageContainer>
        <ErrorState
          message={getApiErrorMessage(policy.error, "تعذر تحميل إعدادات الأتمتة.")}
          onRetry={() => void policy.refetch()}
        />
      </PageContainer>
    );
  }

  return (
    <AutomationForm
      data={policy.data}
      canEdit={settings.data?.can_edit === true}
      channels={channels.data?.items ?? []}
      pages={pages.data?.items ?? []}
      destinationsError={channels.isError || pages.isError}
      onReload={async () => {
        const result = await policy.refetch();
        if (result.error) throw result.error;
        return result.data;
      }}
    />
  );
}

function AutomationForm({
  data,
  canEdit,
  channels,
  pages,
  destinationsError,
  onReload,
}: {
  data: AutomationPolicy;
  canEdit: boolean;
  channels: Channel[];
  pages: FacebookPage[];
  destinationsError: boolean;
  onReload: () => Promise<AutomationPolicy | undefined>;
}) {
  const patch = usePatchAutomationPolicy();
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const [conflict, setConflict] = useState(false);
  const initialValues = useMemo(() => toAutomationFormValues(data), [data]);
  const form = useForm<AutomationFormValues>({
    resolver: zodResolver(automationFormSchema),
    defaultValues: initialValues,
  });
  const { reset } = form;
  const provider = form.watch("destination_provider");
  const destinationId = form.watch("destination_id");

  useEffect(() => {
    if (!form.formState.isDirty) reset(initialValues);
  }, [form.formState.isDirty, initialValues, reset]);

  const destinationOptions = provider === "telegram" ? channels : pages;
  const currentDestination = data.destination;
  const currentOptionPresent = destinationOptions.some((item) => item.id === destinationId);
  const destinationLabel = currentDestination?.label ?? null;

  function selectProvider(value: string) {
    if (value !== "telegram" && value !== "facebook" && value !== "") return;
    form.setValue("destination_provider", value as AutomationFormValues["destination_provider"], {
      shouldDirty: true,
      shouldValidate: true,
    });
    form.setValue("destination_id", "", { shouldDirty: true, shouldValidate: true });
  }

  function resetChanges() {
    form.reset(initialValues);
    setConflict(false);
    setToast(null);
  }

  async function reloadAfterConflict() {
    if (form.formState.isDirty && !window.confirm("سيؤدي التحميل إلى إلغاء التعديلات المحلية غير المحفوظة. هل تريد المتابعة؟")) {
      return;
    }
    try {
      const latest = await onReload();
      if (latest) reset(toAutomationFormValues(latest));
      setConflict(false);
    } catch (error) {
      setToast({
        message: getApiErrorMessage(error, "تعذر تحميل أحدث إعدادات الأتمتة."),
        tone: "error",
      });
    }
  }

  function submit(values: AutomationFormValues) {
    setConflict(false);
    patch.mutate(buildAutomationPatch(values, data), {
      onSuccess: (next) => {
        form.reset(toAutomationFormValues(next));
        setToast({ message: "تم حفظ إعدادات الأتمتة.", tone: "success" });
      },
      onError: (error) => {
        if ((error as ApiError).status === 409) {
          setConflict(true);
          setToast({
            message: "تغيّرت الإعدادات في مساحة العمل. أعد تحميل النسخة الأحدث قبل الحفظ.",
            tone: "error",
          });
          return;
        }
        setToast({
          message: getApiErrorMessage(error, "تعذر حفظ إعدادات الأتمتة."),
          tone: "error",
        });
      },
    });
  }

  return (
    <PageContainer>
      <PageHeader
        title="إعدادات الأتمتة"
        description="احفظ سياسة الاختيار والنشر لمساحة العمل دون تشغيل الأتمتة تلقائياً."
      />

      <div className="space-y-5" dir="rtl">
        <Card className="border-amber-500/40 bg-amber-500/5" role="status">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-600" aria-hidden />
            <div>
              <h2 className="font-semibold">التشغيل التلقائي غير متاح بعد</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                يمكنك حفظ إعدادات الأتمتة الآن، لكن هذا الإصدار لا يشغّل الاكتشاف أو إنشاء المحتوى أو النشر تلقائياً.
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <SectionHeading title="حالة الإعدادات" description="هذه الحالة تعكس الإعداد المحفوظ فقط، وليست حالة تشغيل." />
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatusCard label="حالة السياسة" value={executionStateLabel(data.execution_state)} tone={data.enabled ? "info" : "neutral"} />
            <StatusCard label="جاهزية الإعداد" value={data.configuration_ready ? "جاهزة" : "تحتاج مراجعة"} tone={data.configuration_ready ? "success" : "warning"} />
            <StatusCard label="التنفيذ" value="غير متاح" tone="warning" />
            <StatusCard label="الإصدار" value={String(data.revision)} tone="neutral" />
          </div>
          <label className="mt-5 flex items-start gap-3 rounded-md border border-border p-3">
            <input className="mt-1 size-4 accent-primary" type="checkbox" disabled={!canEdit} {...form.register("enabled")} />
            <span>
              <span className="block text-sm font-medium">الرغبة في تفعيل الأتمتة</span>
              <span className="mt-1 block text-xs text-muted-foreground">هذا يحفظ تفضيلك فقط ولا يبدأ أي تشغيل أو نشر.</span>
            </span>
          </label>
          {!canEdit && <ReadOnlyNotice />}
        </Card>

        <Card>
          <SectionHeading title="معايير اختيار المنتجات" description="تُحفظ هذه الفلاتر لاستخدامها في مرحلة تنفيذ لاحقة." />
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="الكلمات المفتاحية" error={form.formState.errors.keywords?.message} className="sm:col-span-2 lg:col-span-3">
              <Input placeholder="مثال: سماعات لاسلكية" {...form.register("keywords")} disabled={!canEdit} />
            </Field>
            <NumberField label="الحد الأدنى للسعر" name="min_price" form={form} canEdit={canEdit} error={form.formState.errors.min_price?.message} />
            <NumberField label="الحد الأعلى للسعر" name="max_price" form={form} canEdit={canEdit} error={form.formState.errors.max_price?.message} />
            <NumberField label="الحد الأدنى للتقييم" name="min_rating" form={form} canEdit={canEdit} error={form.formState.errors.min_rating?.message} step="0.1" />
            <NumberField label="الحد الأدنى للطلبات" name="min_orders" form={form} canEdit={canEdit} error={form.formState.errors.min_orders?.message} integer />
            <NumberField label="الحد الأدنى للخصم %" name="min_discount" form={form} canEdit={canEdit} error={form.formState.errors.min_discount?.message} step="0.1" />
            <NumberField label="الحد الأدنى للعمولة %" name="min_commission" form={form} canEdit={canEdit} error={form.formState.errors.min_commission?.message} step="0.1" />
            <NumberField label="الحد الأعلى للعمولة %" name="max_commission" form={form} canEdit={canEdit} error={form.formState.errors.max_commission?.message} step="0.1" />
            <NumberField label="عدد المنتجات لكل تشغيل" name="products_per_run" form={form} canEdit={canEdit} error={form.formState.errors.products_per_run?.message} integer />
          </div>
        </Card>

        <Card>
          <SectionHeading title="الجدولة والحدود" description="تفضيلات محفوظة للتنفيذ المستقبلي فقط." />
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="التكرار" error={form.formState.errors.frequency?.message}>
              <Select disabled={!canEdit} {...form.register("frequency")}>
                <option value="daily">يومياً</option>
              </Select>
            </Field>
            <Field label="وقت التشغيل المفضل" error={form.formState.errors.preferred_time_local?.message}>
              <Input dir="ltr" type="time" disabled={!canEdit} {...form.register("preferred_time_local")} />
            </Field>
            <Field label="المنطقة الزمنية المحلولة">
              <Input dir="ltr" value={data.schedule.timezone} readOnly aria-describedby="automation-timezone-help" />
              <span id="automation-timezone-help" className="text-xs text-muted-foreground">موروثة من إعدادات مساحة العمل.</span>
            </Field>
            <NumberField label="الحد اليومي للمنشورات" name="posts_per_day" form={form} canEdit={canEdit} error={form.formState.errors.posts_per_day?.message} integer />
          </div>
        </Card>

        <Card>
          <SectionHeading title="وجهة النشر" description="اختر وجهة واحدة. لا يتم اختيار قناة افتراضية تلقائياً عند تغيير المنصة." />
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Field label="منصة النشر" error={form.formState.errors.destination_provider?.message}>
              <Select disabled={!canEdit} value={provider} onChange={(event) => selectProvider(event.target.value)}>
                <option value="">بدون وجهة</option>
                <option value="telegram">Telegram</option>
                <option value="facebook">Facebook</option>
              </Select>
            </Field>
            <Field label={provider === "facebook" ? "صفحة Facebook" : "قناة Telegram"} error={form.formState.errors.destination_id?.message}>
              <Select disabled={!canEdit || !provider} {...form.register("destination_id")}>
                <option value="">اختر وجهة</option>
                {destinationOptions.map((item) => (
                  <option key={item.id} value={item.id} disabled={!destinationReady(provider, item) && item.id !== destinationId}>
                    {destinationName(provider, item)} — {destinationStatus(provider, item)}
                  </option>
                ))}
                {destinationId && !currentOptionPresent && destinationLabel && (
                  <option value={destinationId}>{destinationLabel} — الحالة المحفوظة</option>
                )}
              </Select>
            </Field>
          </div>
          {destinationsError && <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">تعذر تحميل بعض الوجهات. لا تغيّر الوجهة المحفوظة دون التحقق من صفحة القنوات.</p>}
          {currentDestination && <DestinationStatus destination={currentDestination} />}
          {!currentDestination && !provider && <p className="mt-3 text-sm text-muted-foreground">لا توجد وجهة محفوظة حالياً.</p>}
          {data.warnings.length > 0 && (
            <ul className="mt-4 space-y-2 rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm" aria-label="تحذيرات الإعدادات">
              {data.warnings.map((warning) => <li key={warning}>⚠ {warning}</li>)}
            </ul>
          )}
        </Card>

        <Card>
          <SectionHeading title="إعدادات المحتوى" description="اترك الحقل على الوراثة لاستخدام إعدادات مساحة العمل عند تنفيذ مرحلة لاحقة." />
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <ContentSelect label="مزوّد الذكاء الاصطناعي" name="ai_provider" form={form} canEdit={canEdit} options={[["openai", "OpenAI"], ["gemini", "Gemini"]]} />
            <ContentSelect label="لغة المحتوى" name="language" form={form} canEdit={canEdit} options={[["ar", "العربية"], ["en", "English"], ["fr", "Français"], ["de", "Deutsch"]]} />
            <ContentSelect label="النبرة" name="tone" form={form} canEdit={canEdit} options={[["professional", "احترافية"], ["friendly", "ودية"], ["luxury", "فاخرة"], ["technical", "تقنية"], ["urgent", "عاجلة"], ["minimal", "مختصرة"], ["persuasive", "إقناعية"], ["funny", "مرحة"]]} />
            <ContentSelect label="نوع المحتوى" name="content_type" form={form} canEdit={canEdit} options={[["social", "اجتماعي"], ["description", "وصف"], ["telegram", "Telegram"], ["facebook", "Facebook"], ["blog", "مدونة"], ["email", "بريد إلكتروني"]]} />
            <ContentSelect label="طول المحتوى" name="length" form={form} canEdit={canEdit} options={[["short", "قصير"], ["medium", "متوسط"], ["long", "طويل"]]} />
          </div>
        </Card>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" disabled={!canEdit} loading={patch.isPending} onClick={() => void form.handleSubmit(submit)()}>
            حفظ التغييرات
          </Button>
          <Button type="button" variant="outline" disabled={!form.formState.isDirty || patch.isPending} onClick={resetChanges}>إلغاء التعديلات</Button>
          {conflict && <Button type="button" variant="outline" onClick={() => void reloadAfterConflict()}>تحميل آخر إعدادات</Button>}
          {!canEdit && <span className="text-sm text-muted-foreground"><LockKeyhole className="me-1 inline size-4" aria-hidden />القراءة متاحة، والتعديل لمالك مساحة العمل أو المسؤول.</span>}
        </div>
        {conflict && <p className="text-sm text-destructive" role="alert">لن تتم إعادة المحاولة تلقائياً. حمّل النسخة الأحدث ثم أعد إدخال التغييرات المطلوبة.</p>}
      </div>
      <ToastOverlay message={toast?.message ?? null} tone={toast?.tone} onDismiss={() => setToast(null)} />
    </PageContainer>
  );
}

function SectionHeading({ title, description }: { title: string; description: string }) {
  return <div><h2 className="text-lg font-semibold">{title}</h2><p className="mt-1 text-sm text-muted-foreground">{description}</p></div>;
}

function StatusCard({ label, value, tone }: { label: string; value: string; tone: "neutral" | "success" | "warning" | "info" }) {
  return <div className="rounded-md border border-border p-3"><p className="text-xs text-muted-foreground">{label}</p><Badge className="mt-2" tone={tone}>{value}</Badge></div>;
}

function ReadOnlyNotice() {
  return <p className="mt-4 rounded-md bg-muted p-3 text-sm text-muted-foreground">يمكنك مراجعة الإعدادات، لكن لا تملك صلاحية حفظها في مساحة العمل الحالية.</p>;
}

function Field({ label, error, children, className }: { label: string; error?: string; children: ReactNode; className?: string }) {
  return <div className={className ?? fieldClass}><label className="grid gap-1.5 text-sm font-medium"><span>{label}</span>{children}</label>{error && <p className="text-sm text-destructive" role="alert">{error}</p>}</div>;
}

function NumberField({ label, name, form, canEdit, error, step = "0.01", integer = false }: { label: string; name: "min_price" | "max_price" | "min_rating" | "min_orders" | "min_discount" | "min_commission" | "max_commission" | "products_per_run" | "posts_per_day"; form: ReturnType<typeof useForm<AutomationFormValues>>; canEdit: boolean; error?: string; step?: string; integer?: boolean }) {
  const registration = form.register(name, integer && name !== "min_orders" ? { valueAsNumber: true } : undefined);
  return <Field label={label} error={error}><Input dir="ltr" type="number" min={0} step={integer ? 1 : step} disabled={!canEdit} {...registration} /></Field>;
}

function ContentSelect({ label, name, form, canEdit, options }: { label: string; name: "ai_provider" | "language" | "tone" | "content_type" | "length"; form: ReturnType<typeof useForm<AutomationFormValues>>; canEdit: boolean; options: ReadonlyArray<readonly [string, string]> }) {
  return <Field label={label}><Select disabled={!canEdit} {...form.register(name)}><option value="">استخدام إعدادات مساحة العمل الافتراضي</option>{options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</Select></Field>;
}

function DestinationStatus({ destination }: { destination: AutomationDestination }) {
  return <div className="mt-4 flex flex-wrap items-center gap-2 text-sm"><Badge tone={destination.ready ? "success" : "warning"}>{destinationStatusLabel(destination.status)}</Badge><span className="text-muted-foreground">{destination.label ?? "وجهة محفوظة"}</span>{!destination.ready && <span className="text-amber-700 dark:text-amber-300">تحقق من إعداد الوجهة قبل تفعيل التفضيل.</span>}</div>;
}

function destinationReady(provider: string, item: Channel | FacebookPage) {
  if (provider === "telegram") {
    const channel = item as Channel;
    return channel.is_active && channel.can_post_messages && ["granted", "partial"].includes(channel.bot_permission_status);
  }
  const page = item as FacebookPage;
  return page.is_active && page.validation_status === "valid";
}

function destinationName(provider: string, item: Channel | FacebookPage) {
  if (provider === "telegram") {
    const channel = item as Channel;
    return channel.title || channel.username || channel.telegram_channel_id;
  }
  return (item as FacebookPage).page_name;
}

function destinationStatus(provider: string, item: Channel | FacebookPage) {
  if (destinationReady(provider, item)) return "جاهزة";
  if (provider === "telegram") {
    const channel = item as Channel;
    return channel.is_active ? "صلاحيات غير مكتملة" : "غير نشطة";
  }
  const page = item as FacebookPage;
  return page.is_active ? "غير متحققة" : "غير نشطة";
}

function destinationStatusLabel(status: AutomationDestination["status"]) {
  const labels: Record<AutomationDestination["status"], string> = {
    ready: "الوجهة جاهزة",
    missing: "الوجهة مفقودة",
    inactive: "الوجهة غير نشطة",
    permission_missing: "صلاحيات Telegram غير مكتملة",
    not_validated: "صفحة Facebook غير متحققة",
    unknown: "حالة غير معروفة",
  };
  return labels[status];
}

function executionStateLabel(state: AutomationPolicy["execution_state"]) {
  const labels: Record<AutomationPolicy["execution_state"], string> = {
    disabled: "محفوظة دون تفعيل",
    configured_not_ready: "تحتاج مراجعة",
    configured_ready_not_active: "جاهزة دون تشغيل",
  };
  return labels[state];
}

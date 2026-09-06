"use client";

import { useEffect, useState, type ReactNode } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import {
  ErrorState,
  LoadingState,
  NoActiveWorkspaceState,
} from "@/components/common/states";
import { ToastOverlay } from "@/components/common/ToastOverlay";
import { Badge, Button, Card, Input, Select } from "@/components/ui/primitives";
import { usePlatformReadiness } from "@/features/categories/hooks/useCategories";
import { useChannels } from "@/features/channels/hooks/useChannels";
import { getApiErrorMessage } from "@/services/api-client";
import { useActiveWorkspaceId } from "@/lib/workspace";
import { ConnectionStatusBadges } from "./ConnectionStatusBadges";
import {
  usePatchWorkspaceSettings,
  useWorkspaceSettings,
} from "../hooks/useWorkspaceSettings";
import { applyApiFieldErrors } from "../lib/mapApiErrors";
import {
  AI_PROVIDERS,
  CONTENT_LANGUAGES,
  CONTENT_LENGTHS,
  CONTENT_TYPES,
  DISCOVERY_MODES,
  TIMEZONES,
  TONE_PROFILES,
  UI_LANGUAGES,
  aiDefaultsSchema,
  aliexpressDisplaySchema,
  discoveryDefaultsSchema,
  schedulingDefaultsSchema,
  telegramDefaultsSchema,
  workspaceGeneralSchema,
  type AiDefaultsValues,
  type AliExpressDisplayValues,
  type DiscoveryDefaultsValues,
  type SchedulingDefaultsValues,
  type TelegramDefaultsValues,
  type WorkspaceGeneralValues,
} from "../lib/schemas";
import type { SettingsSection, WorkspaceSettings } from "../types/api";

const COPY: Record<SettingsSection, { title: string; description: string }> = {
  general: {
    title: "الإعدادات العامة",
    description: "تفضيلات واجهة مساحة العمل والمنطقة الزمنية.",
  },
  aliexpress: {
    title: "AliExpress",
    description: "تفضيلات عرض الاكتشاف والاستيراد لهذه المساحة.",
  },
  ai: {
    title: "مزوّدو الذكاء الاصطناعي",
    description: "افتراضيات إنشاء المحتوى لهذه المساحة.",
  },
  telegram: {
    title: "Telegram",
    description: "قناة النشر الافتراضية وحالة البوت.",
  },
  discovery: {
    title: "الاكتشاف",
    description: "وضع الاكتشاف الافتراضي وحجم الصفحة.",
  },
  scheduling: {
    title: "الجدولة",
    description: "المنطقة الزمنية المستخدمة عند جدولة النشر.",
  },
};

function coerceTimezone(value: string): (typeof TIMEZONES)[number] {
  return (TIMEZONES as readonly string[]).includes(value)
    ? (value as (typeof TIMEZONES)[number])
    : "UTC";
}

export function WorkspaceSettingsView({ section }: { section: SettingsSection }) {
  const workspaceId = useActiveWorkspaceId();
  const settings = useWorkspaceSettings();
  const copy = COPY[section];

  if (!workspaceId) {
    return (
      <Card>
        <h2 className="text-lg font-semibold">{copy.title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{copy.description}</p>
        <div className="mt-6">
          <NoActiveWorkspaceState />
        </div>
      </Card>
    );
  }

  if (settings.isPending) return <LoadingState rows={4} />;
  if (settings.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(settings.error, "تعذر تحميل الإعدادات.")}
        onRetry={() => void settings.refetch()}
      />
    );
  }

  return (
    <SettingsSectionCard section={section} data={settings.data} copy={copy} />
  );
}

function SettingsSectionCard({
  section,
  data,
  copy,
}: {
  section: SettingsSection;
  data: WorkspaceSettings;
  copy: { title: string; description: string };
}) {
  const readiness = usePlatformReadiness();
  const showReady = section === "general" || section === "aliexpress" || section === "ai" || section === "telegram";
  const ready = showReady ? readiness.data?.status === "ready" : undefined;

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{copy.title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{copy.description}</p>
        </div>
        {showReady && !readiness.isPending && !readiness.isError && (
          <Badge tone={ready ? "success" : "warning"}>
            {ready ? "الخدمات الأساسية جاهزة" : "الخدمات الأساسية غير جاهزة"}
          </Badge>
        )}
      </div>
      <div className="mt-4">
        <ConnectionStatusBadges section={section} connections={data.connections} />
      </div>
      <div className="mt-6">
        {section === "general" && <GeneralForm data={data} />}
        {section === "aliexpress" && <AliExpressForm data={data} />}
        {section === "ai" && <AiForm data={data} />}
        {section === "telegram" && <TelegramForm data={data} />}
        {section === "discovery" && <DiscoveryForm data={data} />}
        {section === "scheduling" && <SchedulingForm data={data} />}
      </div>
      <p className="mt-6 rounded-md border border-border p-4 text-sm text-muted-foreground">
        شارات الاتصال تعني فقط أن متغير البيئة مضبوط على الخادم، ولا تعرض أي سر.
        مفاتيح JWT وTelegram وAliExpress وOpenAI وGemini تُدار من بيئة الخادم فقط.
      </p>
    </Card>
  );
}

function GeneralForm({ data }: { data: WorkspaceSettings }) {
  const patch = usePatchWorkspaceSettings();
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<WorkspaceGeneralValues>({
    resolver: zodResolver(workspaceGeneralSchema),
    defaultValues: {
      timezone: coerceTimezone(data.timezone),
      ui_language: data.ui_language,
    },
  });

  useEffect(() => {
    reset({
      timezone: coerceTimezone(data.timezone),
      ui_language: data.ui_language,
    });
  }, [data, reset]);

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={handleSubmit((values) => {
        patch.mutate(values, {
          onSuccess: () => setToast({ message: "تم حفظ الإعدادات.", tone: "success" }),
          onError: (error) => {
            const mapped = applyApiFieldErrors(error, setError, ["timezone", "ui_language"]);
            if (!mapped) {
              setToast({
                message: getApiErrorMessage(error, "تعذر حفظ الإعدادات."),
                tone: "error",
              });
            }
          },
        });
      })}
    >
      <Field label="المنطقة الزمنية" error={errors.timezone?.message}>
        <Select disabled={!data.can_edit} {...register("timezone")}>
          {TIMEZONES.map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="لغة الواجهة" error={errors.ui_language?.message}>
        <Select disabled={!data.can_edit} {...register("ui_language")}>
          {UI_LANGUAGES.map((lang) => (
            <option key={lang} value={lang}>
              {lang === "ar" ? "العربية" : "English"}
            </option>
          ))}
        </Select>
      </Field>
      <SubmitRow canEdit={data.can_edit} loading={patch.isPending} />
      <ToastOverlay
        message={toast?.message ?? null}
        tone={toast?.tone}
        onDismiss={() => setToast(null)}
      />
    </form>
  );
}

function AliExpressForm({ data }: { data: WorkspaceSettings }) {
  const patch = usePatchWorkspaceSettings();
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<AliExpressDisplayValues>({
    resolver: zodResolver(aliexpressDisplaySchema),
    defaultValues: {
      aliexpress_target_currency: data.aliexpress_target_currency,
      aliexpress_ship_to_country: data.aliexpress_ship_to_country,
      aliexpress_target_language: data.aliexpress_target_language,
    },
  });

  useEffect(() => {
    reset({
      aliexpress_target_currency: data.aliexpress_target_currency,
      aliexpress_ship_to_country: data.aliexpress_ship_to_country,
      aliexpress_target_language: data.aliexpress_target_language,
    });
  }, [data, reset]);

  return (
    <form
      className="grid gap-4 sm:grid-cols-3"
      onSubmit={handleSubmit((values) => {
        patch.mutate(
          {
            aliexpress_target_currency: values.aliexpress_target_currency.toUpperCase(),
            aliexpress_ship_to_country: values.aliexpress_ship_to_country.toUpperCase(),
            aliexpress_target_language: values.aliexpress_target_language.toUpperCase(),
          },
          {
            onSuccess: () => setToast({ message: "تم حفظ الإعدادات.", tone: "success" }),
            onError: (error) => {
              const mapped = applyApiFieldErrors(error, setError, [
                "aliexpress_target_currency",
                "aliexpress_ship_to_country",
                "aliexpress_target_language",
              ]);
              if (!mapped) {
                setToast({
                  message: getApiErrorMessage(error, "تعذر حفظ الإعدادات."),
                  tone: "error",
                });
              }
            },
          },
        );
      })}
    >
      <Field label="العملة المستهدفة" error={errors.aliexpress_target_currency?.message}>
        <Input
          dir="ltr"
          disabled={!data.can_edit}
          maxLength={3}
          {...register("aliexpress_target_currency")}
        />
      </Field>
      <Field label="بلد الشحن" error={errors.aliexpress_ship_to_country?.message}>
        <Input
          dir="ltr"
          disabled={!data.can_edit}
          maxLength={2}
          {...register("aliexpress_ship_to_country")}
        />
      </Field>
      <Field label="لغة العرض" error={errors.aliexpress_target_language?.message}>
        <Input
          dir="ltr"
          disabled={!data.can_edit}
          maxLength={8}
          {...register("aliexpress_target_language")}
        />
      </Field>
      <SubmitRow canEdit={data.can_edit} loading={patch.isPending} />
      <ToastOverlay
        message={toast?.message ?? null}
        tone={toast?.tone}
        onDismiss={() => setToast(null)}
      />
    </form>
  );
}

function AiForm({ data }: { data: WorkspaceSettings }) {
  const patch = usePatchWorkspaceSettings();
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<AiDefaultsValues>({
    resolver: zodResolver(aiDefaultsSchema),
    defaultValues: {
      default_ai_provider: data.default_ai_provider,
      default_content_type: data.default_content_type,
      default_tone: data.default_tone,
      default_content_language: data.default_content_language,
      default_content_length: data.default_content_length,
    },
  });

  useEffect(() => {
    reset({
      default_ai_provider: data.default_ai_provider,
      default_content_type: data.default_content_type,
      default_tone: data.default_tone,
      default_content_language: data.default_content_language,
      default_content_length: data.default_content_length,
    });
  }, [data, reset]);

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={handleSubmit((values) => {
        patch.mutate(values, {
          onSuccess: () => setToast({ message: "تم حفظ الإعدادات.", tone: "success" }),
          onError: (error) => {
            const mapped = applyApiFieldErrors(error, setError, [
              "default_ai_provider",
              "default_content_type",
              "default_tone",
              "default_content_language",
              "default_content_length",
            ]);
            if (!mapped) {
              setToast({
                message: getApiErrorMessage(error, "تعذر حفظ الإعدادات."),
                tone: "error",
              });
            }
          },
        });
      })}
    >
      <Field label="المزوّد الافتراضي" error={errors.default_ai_provider?.message}>
        <Select disabled={!data.can_edit} {...register("default_ai_provider")}>
          {AI_PROVIDERS.map((value) => (
            <option key={value} value={value}>
              {value === "openai" ? "OpenAI" : "Gemini"}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="نوع المحتوى" error={errors.default_content_type?.message}>
        <Select disabled={!data.can_edit} {...register("default_content_type")}>
          {CONTENT_TYPES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="النبرة" error={errors.default_tone?.message}>
        <Select disabled={!data.can_edit} {...register("default_tone")}>
          {TONE_PROFILES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="لغة المحتوى" error={errors.default_content_language?.message}>
        <Select disabled={!data.can_edit} {...register("default_content_language")}>
          {CONTENT_LANGUAGES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="الطول" error={errors.default_content_length?.message}>
        <Select disabled={!data.can_edit} {...register("default_content_length")}>
          {CONTENT_LENGTHS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </Field>
      <SubmitRow canEdit={data.can_edit} loading={patch.isPending} />
      <ToastOverlay
        message={toast?.message ?? null}
        tone={toast?.tone}
        onDismiss={() => setToast(null)}
      />
    </form>
  );
}

function TelegramForm({ data }: { data: WorkspaceSettings }) {
  const patch = usePatchWorkspaceSettings();
  const channels = useChannels();
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<TelegramDefaultsValues>({
    resolver: zodResolver(telegramDefaultsSchema),
    defaultValues: {
      default_telegram_channel_id: data.default_telegram_channel_id ?? "",
    },
  });

  useEffect(() => {
    reset({ default_telegram_channel_id: data.default_telegram_channel_id ?? "" });
  }, [data, reset]);

  return (
    <form
      className="grid gap-4"
      onSubmit={handleSubmit((values) => {
        patch.mutate(
          {
            default_telegram_channel_id:
              values.default_telegram_channel_id === ""
                ? null
                : values.default_telegram_channel_id,
          },
          {
            onSuccess: () => setToast({ message: "تم حفظ الإعدادات.", tone: "success" }),
            onError: (error) => {
              const mapped = applyApiFieldErrors(error, setError, [
                "default_telegram_channel_id",
              ]);
              if (!mapped) {
                setToast({
                  message: getApiErrorMessage(error, "تعذر حفظ الإعدادات."),
                  tone: "error",
                });
              }
            },
          },
        );
      })}
    >
      <Field label="القناة الافتراضية" error={errors.default_telegram_channel_id?.message}>
        <Select disabled={!data.can_edit} {...register("default_telegram_channel_id")}>
          <option value="">بدون قناة افتراضية</option>
          {(channels.data?.items ?? []).map((channel) => (
            <option key={channel.id} value={channel.id}>
              {channel.title || channel.username || channel.telegram_channel_id}
            </option>
          ))}
        </Select>
      </Field>
      <p className="text-sm text-muted-foreground">
        صلاحيات القنوات تُدار من صفحة القنوات. رمز البوت لا يُعرض ولا يُعدّل من هنا.
      </p>
      <SubmitRow canEdit={data.can_edit} loading={patch.isPending} />
      <ToastOverlay
        message={toast?.message ?? null}
        tone={toast?.tone}
        onDismiss={() => setToast(null)}
      />
    </form>
  );
}

function DiscoveryForm({ data }: { data: WorkspaceSettings }) {
  const patch = usePatchWorkspaceSettings();
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<DiscoveryDefaultsValues>({
    resolver: zodResolver(discoveryDefaultsSchema),
    defaultValues: {
      discovery_default_mode: data.discovery_default_mode,
      discovery_page_size: data.discovery_page_size,
    },
  });

  useEffect(() => {
    reset({
      discovery_default_mode: data.discovery_default_mode,
      discovery_page_size: data.discovery_page_size,
    });
  }, [data, reset]);

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={handleSubmit((values) => {
        patch.mutate(values, {
          onSuccess: () => setToast({ message: "تم حفظ الإعدادات.", tone: "success" }),
          onError: (error) => {
            const mapped = applyApiFieldErrors(error, setError, [
              "discovery_default_mode",
              "discovery_page_size",
            ]);
            if (!mapped) {
              setToast({
                message: getApiErrorMessage(error, "تعذر حفظ الإعدادات."),
                tone: "error",
              });
            }
          },
        });
      })}
    >
      <Field label="وضع الاكتشاف الافتراضي" error={errors.discovery_default_mode?.message}>
        <Select disabled={!data.can_edit} {...register("discovery_default_mode")}>
          {DISCOVERY_MODES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="عدد النتائج في الصفحة" error={errors.discovery_page_size?.message}>
        <Input
          dir="ltr"
          disabled={!data.can_edit}
          min={1}
          max={50}
          type="number"
          {...register("discovery_page_size", { valueAsNumber: true })}
        />
      </Field>
      <SubmitRow canEdit={data.can_edit} loading={patch.isPending} />
      <ToastOverlay
        message={toast?.message ?? null}
        tone={toast?.tone}
        onDismiss={() => setToast(null)}
      />
    </form>
  );
}

function SchedulingForm({ data }: { data: WorkspaceSettings }) {
  const patch = usePatchWorkspaceSettings();
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<SchedulingDefaultsValues>({
    resolver: zodResolver(schedulingDefaultsSchema),
    defaultValues: { timezone: coerceTimezone(data.timezone) },
  });

  useEffect(() => {
    reset({ timezone: coerceTimezone(data.timezone) });
  }, [data, reset]);

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={handleSubmit((values) => {
        patch.mutate(values, {
          onSuccess: () => setToast({ message: "تم حفظ الإعدادات.", tone: "success" }),
          onError: (error) => {
            const mapped = applyApiFieldErrors(error, setError, ["timezone"]);
            if (!mapped) {
              setToast({
                message: getApiErrorMessage(error, "تعذر حفظ الإعدادات."),
                tone: "error",
              });
            }
          },
        });
      })}
    >
      <Field label="منطقة وقت الجدولة" error={errors.timezone?.message}>
        <Select disabled={!data.can_edit} {...register("timezone")}>
          {TIMEZONES.map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </Select>
      </Field>
      <p className="sm:col-span-2 text-sm text-muted-foreground">
        حالات قائمة الانتظار (مسودة، انتظار، مجدول، منشور) ليست إعداداً قابلاً للتعديل. وتيرة
        العامل تبقى في بيئة الخادم.
      </p>
      <SubmitRow canEdit={data.can_edit} loading={patch.isPending} />
      <ToastOverlay
        message={toast?.message ?? null}
        tone={toast?.tone}
        onDismiss={() => setToast(null)}
      />
    </form>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm">{label}</label>
      {children}
      {error && (
        <p className="mt-1 text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function SubmitRow({ canEdit, loading }: { canEdit: boolean; loading: boolean }) {
  return (
    <div className="sm:col-span-full flex flex-wrap items-center gap-3">
      <Button disabled={!canEdit} loading={loading} type="submit">
        حفظ
      </Button>
      {!canEdit && (
        <p className="text-sm text-muted-foreground">
          التعديل متاح لمالك مساحة العمل أو حساب المسؤول فقط.
        </p>
      )}
    </div>
  );
}

"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Bot, RefreshCw } from "lucide-react";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  NoActiveWorkspaceState,
} from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Button, Card, Input } from "@/components/ui/primitives";
import {
  useChannels,
  useCreateChannel,
  useRefreshChannelPermissions,
  useUpdateChannel,
} from "../hooks/useChannels";
import { getApiErrorMessage } from "@/services/api-client";
import { useActiveWorkspaceId } from "@/lib/workspace";
import { useWorkspaceSettings } from "@/features/settings/hooks/useWorkspaceSettings";

const schema = z.object({
  telegram_channel_id: z.string().min(1, "معرّف القناة مطلوب").max(64),
  title: z.string().max(255).optional(),
});
type Values = z.infer<typeof schema>;

const permissionLabels = {
  unknown: "غير معروف",
  pending: "قيد الفحص",
  granted: "ممنوحة",
  partial: "جزئية",
  denied: "مرفوضة",
} as const;

export function ChannelsView() {
  const workspaceId = useActiveWorkspaceId();
  const channels = useChannels();
  const settings = useWorkspaceSettings();
  const create = useCreateChannel();
  const update = useUpdateChannel();
  const refresh = useRefreshChannelPermissions();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  if (!workspaceId) {
    return (
      <PageContainer>
        <PageHeader title="قنوات Telegram" description="أدر وجهات النشر وصلاحيات البوت." />
        <NoActiveWorkspaceState />
      </PageContainer>
    );
  }

  const defaultChannelId = settings.data?.default_telegram_channel_id;

  return (
    <PageContainer>
      <PageHeader title="قنوات Telegram" description="أدر وجهات النشر وصلاحيات البوت." />
      <Card className="mb-6">
        <h2 className="mb-2 font-semibold">إضافة قناة</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          أضف البوت إلى القناة كمسؤول مع صلاحية إرسال الرسائل، ثم افحص الصلاحيات واختر القناة
          الافتراضية من إعدادات Telegram.
        </p>
        <form
          className="grid gap-4 md:grid-cols-[1fr_1fr_auto]"
          onSubmit={handleSubmit((values) =>
            create.mutate(
              { ...values, is_active: true },
              { onSuccess: () => reset() },
            ),
          )}
        >
          <div>
            <label className="mb-1.5 block text-sm" htmlFor="channelId">
              معرّف القناة
            </label>
            <Input
              id="channelId"
              dir="ltr"
              placeholder="@channel أو -100..."
              {...register("telegram_channel_id")}
            />
            {errors.telegram_channel_id && (
              <p className="mt-1 text-sm text-destructive">
                {errors.telegram_channel_id.message}
              </p>
            )}
          </div>
          <div>
            <label className="mb-1.5 block text-sm" htmlFor="channelTitle">
              الاسم (اختياري)
            </label>
            <Input id="channelTitle" {...register("title")} />
          </div>
          <Button className="self-end" loading={create.isPending} type="submit">
            إضافة القناة
          </Button>
        </form>
        {create.isError && (
          <p className="mt-3 text-sm text-destructive" role="alert">
            {getApiErrorMessage(create.error, "تعذر إضافة القناة.")}
          </p>
        )}
      </Card>

      {settings.isError && (
        <p className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
          تعذر تحميل حالة القناة الافتراضية: {getApiErrorMessage(settings.error, "تعذر تحميل الإعدادات.")}
        </p>
      )}

      {channels.isPending ? (
        <LoadingState />
      ) : channels.isError ? (
        <ErrorState
          message={getApiErrorMessage(channels.error, "تعذر تحميل القنوات.")}
          onRetry={() => void channels.refetch()}
        />
      ) : channels.data.items.length === 0 ? (
        <EmptyState
          title="لا توجد قنوات"
          description="أضف قناة Telegram، امنح البوت صلاحية النشر، ثم اخترها كقناة افتراضية من الإعدادات."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {channels.data.items.map((channel) => {
            const isDefault = defaultChannelId === channel.id;
            const canPublish = channel.is_active && channel.can_post_messages;
            const needsSetup = !channel.is_active || !canPublish || !isDefault;
            const refreshSucceeded = refresh.isSuccess && refresh.variables === channel.id;
            const refreshFailed = refresh.isError && refresh.variables === channel.id;

            return (
              <Card key={channel.id}>
                <div className="flex items-start justify-between gap-3">
                  <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
                    <Bot className="size-5" />
                  </div>
                  <div className="flex flex-wrap justify-end gap-2">
                    <Badge tone={channel.is_active ? "success" : "warning"}>
                      {channel.is_active ? "نشطة" : "غير نشطة"}
                    </Badge>
                    <Badge
                      tone={
                        channel.bot_permission_status === "granted"
                          ? "success"
                          : channel.bot_permission_status === "denied"
                            ? "error"
                            : "warning"
                      }
                    >
                      الصلاحيات: {permissionLabels[channel.bot_permission_status]}
                    </Badge>
                    {isDefault && <Badge tone="info">الافتراضية</Badge>}
                  </div>
                </div>
                <h2 className="mt-4 font-semibold">
                  {channel.title || channel.username || channel.telegram_channel_id}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground" dir="ltr">
                  {channel.telegram_channel_id}
                </p>

                {needsSetup && (
                  <div className="mt-4 rounded-md border border-amber-300/60 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
                    <p className="font-medium">إكمال إعداد القناة</p>
                    <ul className="mt-1 list-inside list-disc space-y-1">
                      {!channel.is_active && <li>فعّل القناة.</li>}
                      {!channel.can_post_messages && <li>امنح البوت صلاحية إرسال الرسائل.</li>}
                      {!isDefault && <li>اخترها كقناة افتراضية من إعدادات Telegram.</li>}
                    </ul>
                    {channel.permission_detail && (
                      <p className="mt-2 text-xs">{channel.permission_detail}</p>
                    )}
                  </div>
                )}

                {refreshSucceeded && (
                  <p className="mt-3 text-sm text-emerald-700" role="status">
                    تم تحديث صلاحيات القناة.
                  </p>
                )}
                {refreshFailed && (
                  <p className="mt-3 text-sm text-destructive" role="alert">
                    {getApiErrorMessage(refresh.error, "تعذر فحص صلاحيات القناة.")}
                  </p>
                )}

                <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
                  <span className="text-sm">
                    {canPublish ? "جاهزة للنشر" : "تحتاج إلى إعداد"}
                  </span>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      loading={refresh.isPending && refresh.variables === channel.id}
                      onClick={() => refresh.mutate(channel.id)}
                    >
                      <RefreshCw className="size-4" aria-hidden />
                      إعادة فحص الصلاحيات
                    </Button>
                    <Button
                      variant="outline"
                      loading={update.isPending && update.variables?.id === channel.id}
                      onClick={() =>
                        update.mutate({
                          id: channel.id,
                          input: { is_active: !channel.is_active },
                        })
                      }
                    >
                      {channel.is_active ? "تعطيل" : "تفعيل"}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </PageContainer>
  );
}

"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Bot } from "lucide-react";
import { EmptyState, ErrorState, LoadingState, NoActiveWorkspaceState } from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Button, Card, Input } from "@/components/ui/primitives";
import { useChannels, useCreateChannel, useUpdateChannel } from "../hooks/useChannels";
import { getApiErrorMessage } from "@/services/api-client";
import { useActiveWorkspaceId } from "@/lib/workspace";

const schema = z.object({
  telegram_channel_id: z.string().min(1, "معرّف القناة مطلوب").max(64),
  title: z.string().max(255).optional(),
});
type Values = z.infer<typeof schema>;

export function ChannelsView() {
  const workspaceId = useActiveWorkspaceId();
  const channels = useChannels();
  const create = useCreateChannel();
  const update = useUpdateChannel();
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema) });
  if (!workspaceId) {
    return (
      <PageContainer>
        <PageHeader title="قنوات Telegram" description="أدر وجهات النشر وصلاحيات البوت." />
        <NoActiveWorkspaceState />
      </PageContainer>
    );
  }
  return (
    <PageContainer>
      <PageHeader title="قنوات Telegram" description="أدر وجهات النشر وصلاحيات البوت." />
      <Card className="mb-6">
        <h2 className="mb-4 font-semibold">إضافة قناة</h2>
        <form className="grid gap-4 md:grid-cols-[1fr_1fr_auto]" onSubmit={handleSubmit((values) => create.mutate({ ...values, is_active: true }, { onSuccess: () => reset() }))}>
          <div><label className="mb-1.5 block text-sm" htmlFor="channelId">معرّف القناة</label><Input id="channelId" dir="ltr" placeholder="@channel أو -100..." {...register("telegram_channel_id")} />{errors.telegram_channel_id && <p className="mt-1 text-sm text-destructive">{errors.telegram_channel_id.message}</p>}</div>
          <div><label className="mb-1.5 block text-sm" htmlFor="channelTitle">الاسم (اختياري)</label><Input id="channelTitle" {...register("title")} /></div>
          <Button className="self-end" loading={create.isPending} type="submit">إضافة القناة</Button>
        </form>
        {create.isError && <p className="mt-3 text-sm text-destructive" role="alert">{getApiErrorMessage(create.error, "تعذر إضافة القناة.")}</p>}
      </Card>
      {channels.isPending ? <LoadingState /> : channels.isError ? <ErrorState message={getApiErrorMessage(channels.error, "تعذر تحميل القنوات.")} onRetry={() => void channels.refetch()} /> : channels.data.items.length === 0 ? <EmptyState title="لا توجد قنوات" description="أضف قناة Telegram لبدء النشر." /> : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {channels.data.items.map((channel) => (
            <Card key={channel.id}>
              <div className="flex items-start justify-between"><div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary"><Bot className="size-5" /></div><Badge tone={channel.bot_permission_status === "granted" ? "success" : channel.bot_permission_status === "denied" ? "error" : "warning"}>{channel.bot_permission_status}</Badge></div>
              <h2 className="mt-4 font-semibold">{channel.title || channel.username || channel.telegram_channel_id}</h2>
              <p className="mt-1 text-sm text-muted-foreground" dir="ltr">{channel.telegram_channel_id}</p>
              <div className="mt-5 flex items-center justify-between border-t border-border pt-4"><span className="text-sm">{channel.can_post_messages ? "جاهزة للنشر" : "تحتاج صلاحية النشر"}</span><Button variant="outline" loading={update.isPending && update.variables?.id === channel.id} onClick={() => update.mutate({ id: channel.id, input: { is_active: !channel.is_active } })}>{channel.is_active ? "تعطيل" : "تفعيل"}</Button></div>
            </Card>
          ))}
        </div>
      )}
    </PageContainer>
  );
}

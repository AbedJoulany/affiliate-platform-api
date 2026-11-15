"use client";

import Link from "next/link";
import { Select } from "@/components/ui/primitives";
import type { Channel, FacebookPage } from "@/features/channels/types/api";
import type { QueueItem, QueueProvider } from "../types/api";

export type DestinationSelection = {
  provider: QueueProvider;
  channelId: string | null;
  facebookPageId: string | null;
};

export function destinationSelectionFromQueue(item: QueueItem): DestinationSelection {
  return {
    provider: item.provider,
    channelId: item.provider === "telegram" ? item.channel_id : null,
    facebookPageId: item.provider === "facebook" ? item.facebook_page_id : null,
  };
}

export function destinationSelectionIsReady(
  selection: DestinationSelection,
  channels: Channel[],
  pages: FacebookPage[],
): boolean {
  if (selection.provider === "telegram") {
    const channel = channels.find((item) => item.id === selection.channelId);
    return Boolean(channel?.is_active && channel.can_post_messages);
  }
  const page = pages.find((item) => item.id === selection.facebookPageId);
  return Boolean(page?.is_active && page.validation_status === "valid");
}

export function destinationSelectionPatch(selection: DestinationSelection) {
  return {
    provider: selection.provider,
    channel_id: selection.provider === "telegram" ? selection.channelId : null,
    facebook_page_id:
      selection.provider === "facebook" ? selection.facebookPageId : null,
  };
}

export function PublishingDestinationSelector({
  value,
  channels,
  pages,
  onChange,
  onBlur,
  disabled = false,
  idPrefix = "publishing-destination",
}: {
  value: DestinationSelection;
  channels: Channel[];
  pages: FacebookPage[];
  onChange: (value: DestinationSelection) => void;
  onBlur?: () => void;
  disabled?: boolean;
  idPrefix?: string;
}) {
  const telegramChannels = channels.filter(
    (channel) => channel.is_active && channel.can_post_messages,
  );
  const facebookPages = pages.filter(
    (page) => page.is_active && page.validation_status === "valid",
  );
  const providerId = idPrefix + "-provider";
  const targetId = idPrefix + "-target";

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div>
        <label className="mb-1.5 block text-sm" htmlFor={providerId}>
          منصة النشر
        </label>
        <Select
          id={providerId}
          value={value.provider}
          disabled={disabled}
          onBlur={onBlur}
          onChange={(event) => {
            const provider = event.target.value as QueueProvider;
            onChange({
              provider,
              channelId: provider === "telegram" ? value.channelId : null,
              facebookPageId: provider === "facebook" ? value.facebookPageId : null,
            });
          }}
        >
          <option value="telegram">Telegram</option>
          <option value="facebook">Facebook</option>
        </Select>
      </div>

      <div>
        <label className="mb-1.5 block text-sm" htmlFor={targetId}>
          الوجهة
        </label>
        {value.provider === "telegram" ? (
          <Select
            id={targetId}
            value={value.channelId ?? ""}
            disabled={disabled}
            onBlur={onBlur}
            onChange={(event) =>
              onChange({ ...value, channelId: event.target.value || null })
            }
          >
            <option value="">اختر قناة Telegram</option>
            {channels.map((channel) => (
              <option
                key={channel.id}
                value={channel.id}
                disabled={!channel.is_active || !channel.can_post_messages}
              >
                {channel.title ?? channel.username ?? channel.telegram_channel_id}
                {!channel.is_active || !channel.can_post_messages ? " (غير جاهزة)" : ""}
              </option>
            ))}
          </Select>
        ) : (
          <Select
            id={targetId}
            value={value.facebookPageId ?? ""}
            disabled={disabled}
            onBlur={onBlur}
            onChange={(event) =>
              onChange({ ...value, facebookPageId: event.target.value || null })
            }
          >
            <option value="">اختر صفحة Facebook</option>
            {pages.map((page) => (
              <option
                key={page.id}
                value={page.id}
                disabled={!page.is_active || page.validation_status !== "valid"}
              >
                {page.page_name}
                {!page.is_active || page.validation_status !== "valid" ? " (غير جاهزة)" : ""}
              </option>
            ))}
          </Select>
        )}
      </div>

      {value.provider === "facebook" && facebookPages.length === 0 ? (
        <p className="text-sm text-muted-foreground sm:col-span-2">
          لا توجد صفحة Facebook نشطة ومتحقق منها.{" "}
          <Link className="text-primary underline" href="/channels">
            افتح إعدادات القنوات
          </Link>
          {pages.length > 0 ? " لمراجعة حالة الصفحات." : " لإضافة صفحة."}
        </p>
      ) : null}

      {value.provider === "telegram" && telegramChannels.length === 0 ? (
        <p className="text-sm text-muted-foreground sm:col-span-2">
          لا توجد قناة Telegram نشطة ومجهزة للنشر.
        </p>
      ) : null}
    </div>
  );
}

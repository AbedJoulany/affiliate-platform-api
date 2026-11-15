import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Channel } from "@/features/channels/types/api";
import type { FacebookPage } from "@/features/channels/types/api";
import {
  PublishingDestinationSelector,
  destinationSelectionFromQueue,
  type DestinationSelection,
} from "./PublishingDestinationSelector";

afterEach(() => {
  cleanup();
});

const PAGE_ID = "550e8400-e29b-41d4-a716-446655440000";
const CHANNEL_ID = "660e8400-e29b-41d4-a716-446655440000";
const selection: DestinationSelection = {
  provider: "facebook",
  channelId: null,
  facebookPageId: PAGE_ID,
};

function makePage(overrides: Partial<FacebookPage> = {}): FacebookPage {
  return {
    id: PAGE_ID,
    workspace_id: "660e8400-e29b-41d4-a716-446655440000",
    facebook_page_id: "123456789",
    page_name: "صفحة الاختبار",
    token_expires_at: null,
    is_active: true,
    validation_status: "valid",
    last_validated_at: "2026-01-01T00:00:00Z",
    last_error: null,
    has_access_token: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeChannel(overrides: Partial<Channel> = {}): Channel {
  return {
    id: CHANNEL_ID,
    telegram_channel_id: "-100123",
    title: "قناة الاختبار",
    username: "test_channel",
    bot_permission_status: "granted",
    can_post_messages: true,
    can_edit_messages: true,
    can_delete_messages: true,
    permissions_checked_at: null,
    permission_detail: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("PublishingDestinationSelector", () => {
  it("treats legacy Queue items without a provider as Telegram", () => {
    const legacyItem = {
      channel_id: CHANNEL_ID,
      facebook_page_id: null,
    } as never;

    expect(destinationSelectionFromQueue(legacyItem)).toEqual({
      provider: "telegram",
      channelId: CHANNEL_ID,
      facebookPageId: null,
    });
  });

  it("keeps Telegram as the default and disables channels that are not ready", () => {
    render(
      <PublishingDestinationSelector
        value={{ provider: "telegram", channelId: CHANNEL_ID, facebookPageId: null }}
        channels={[makeChannel(), makeChannel({ id: "not-ready", title: "غير جاهزة", can_post_messages: false })]}
        pages={[]}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("منصة النشر")).toHaveValue("telegram");
    expect(screen.getByLabelText("الوجهة")).toHaveValue(CHANNEL_ID);
    expect(screen.getByRole("option", { name: /غير جاهزة/ })).toBeDisabled();
  });

  it("allows a validated active Facebook Page and reports provider changes", async () => {
    const onChange = vi.fn();
    render(
      <PublishingDestinationSelector
        value={selection}
        channels={[]}
        pages={[makePage()]}
        onChange={onChange}
      />,
    );

    const target = screen.getByLabelText("الوجهة");
    expect(target).toHaveValue(PAGE_ID);
    expect(screen.getByRole("option", { name: "صفحة الاختبار" })).toBeEnabled();

    await userEvent.selectOptions(screen.getByLabelText("منصة النشر"), "telegram");
    expect(onChange).toHaveBeenCalledWith({
      provider: "telegram",
      channelId: null,
      facebookPageId: null,
    });
  });

  it("disables inactive or unvalidated Facebook Pages", () => {
    render(
      <PublishingDestinationSelector
        value={selection}
        channels={[]}
        pages={[makePage({ is_active: false }), makePage({ id: "invalid", validation_status: "invalid", page_name: "غير صالحة" })]}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("option", { name: /صفحة الاختبار/ })).toBeDisabled();
    expect(screen.getByRole("option", { name: /غير صالحة/ })).toBeDisabled();
    expect(screen.getByText(/لا توجد صفحة Facebook نشطة ومتحقق منها/)).toBeInTheDocument();
  });

  it("guides the operator to Channels when no Facebook Page is ready", () => {
    render(
      <PublishingDestinationSelector
        value={selection}
        channels={[]}
        pages={[]}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("link", { name: "افتح إعدادات القنوات" })).toHaveAttribute(
      "href",
      "/channels",
    );
  });
});

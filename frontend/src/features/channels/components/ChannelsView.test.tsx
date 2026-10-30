import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChannelsView } from "./ChannelsView";
import { getChannels, refreshChannelPermissions } from "../api/channels.api";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";

vi.mock("../api/channels.api", () => ({
  getChannels: vi.fn(),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
  refreshChannelPermissions: vi.fn(),
}));

vi.mock("@/features/settings/hooks/useWorkspaceSettings", () => ({
  useWorkspaceSettings: () => ({
    data: { default_telegram_channel_id: null },
    isError: false,
  }),
}));

const getChannelsMock = vi.mocked(getChannels);
const refreshPermissionsMock = vi.mocked(refreshChannelPermissions);

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(createElement(ChannelsView), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
}

afterEach(() => {
  cleanup();
  session.clear();
  vi.clearAllMocks();
});

describe("ChannelsView workspace gating", () => {
  it("shows no-workspace state and does not fetch without a workspace id", () => {
    renderView();
    expect(screen.getByText("لا توجد مساحة عمل نشطة")).toBeInTheDocument();
    expect(getChannelsMock).not.toHaveBeenCalled();
  });

  it("fetches GET /channels when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getChannelsMock.mockResolvedValue({ items: [], total: 0, skip: 0, limit: 20 });

    renderView();
    await waitFor(() => expect(getChannelsMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("لا توجد قنوات")).toBeInTheDocument();
  });

  it("refreshes permissions for the selected channel", async () => {
    const channel = {
      id: "channel-1",
      telegram_channel_id: "@test-channel",
      title: "Test Channel",
      username: "testchannel",
      bot_permission_status: "unknown" as const,
      can_post_messages: false,
      can_edit_messages: false,
      can_delete_messages: false,
      permissions_checked_at: null,
      permission_detail: null,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    setActiveWorkspaceId(WORKSPACE_A);
    getChannelsMock.mockResolvedValue({ items: [channel], total: 1, skip: 0, limit: 20 });
    refreshPermissionsMock.mockResolvedValue({ ...channel, bot_permission_status: "granted", can_post_messages: true });

    renderView();
    await userEvent.setup().click(await screen.findByRole("button", { name: "إعادة فحص الصلاحيات" }));

    await waitFor(() => expect(refreshPermissionsMock.mock.calls[0]?.[0]).toBe("channel-1"));
  });
});

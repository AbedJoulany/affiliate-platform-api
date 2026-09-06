import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChannelsView } from "./ChannelsView";
import { getChannels } from "../api/channels.api";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";

vi.mock("../api/channels.api", () => ({
  getChannels: vi.fn(),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
}));

const getChannelsMock = vi.mocked(getChannels);

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
});

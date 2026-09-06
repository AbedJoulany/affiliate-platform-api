import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueueView } from "./QueueView";
import { getQueue } from "../api/queue.api";
import { getChannels } from "@/features/channels/api/channels.api";
import { getProducts } from "@/features/products/api/products.api";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) =>
    createElement("a", { href }, children),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("../hooks/useQueueRealtimeInvalidation", () => ({
  useQueueRealtimeInvalidation: () => ({
    status: "disconnected",
    pollingEnabled: false,
  }),
}));

vi.mock("../api/queue.api", () => ({
  getQueue: vi.fn(),
  getQueueItem: vi.fn(),
  getQueuePublishAttempts: vi.fn(),
  createQueueItem: vi.fn(),
  updateQueueItem: vi.fn(),
  deleteQueueItem: vi.fn(),
  publishQueueItem: vi.fn(),
}));

vi.mock("@/features/channels/api/channels.api", () => ({
  getChannels: vi.fn(),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
}));

vi.mock("@/features/products/api/products.api", () => ({
  getProducts: vi.fn(),
  getProduct: vi.fn(),
  updateProduct: vi.fn(),
  deleteProduct: vi.fn(),
}));

const getQueueMock = vi.mocked(getQueue);
const getChannelsMock = vi.mocked(getChannels);
const getProductsMock = vi.mocked(getProducts);

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(createElement(QueueView), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
}

afterEach(() => {
  cleanup();
  session.clear();
  vi.clearAllMocks();
});

describe("QueueView workspace gating", () => {
  it("shows no-workspace state and does not fetch tenant queues", () => {
    getProductsMock.mockResolvedValue({ items: [], total: 0, skip: 0, limit: 200 });
    renderView();
    expect(screen.getByText("لا توجد مساحة عمل نشطة")).toBeInTheDocument();
    expect(getQueueMock).not.toHaveBeenCalled();
    expect(getChannelsMock).not.toHaveBeenCalled();
  });

  it("fetches GET /queues when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getQueueMock.mockResolvedValue({ items: [], total: 0, skip: 0, limit: 200 });
    getChannelsMock.mockResolvedValue({ items: [], total: 0, skip: 0, limit: 20 });
    getProductsMock.mockResolvedValue({ items: [], total: 0, skip: 0, limit: 200 });

    renderView();
    await waitFor(() => expect(getQueueMock).toHaveBeenCalledTimes(1));
  });
});

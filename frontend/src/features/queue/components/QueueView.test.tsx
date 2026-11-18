import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueueView } from "./QueueView";
import { getQueue } from "../api/queue.api";
import { getQueueItem, getQueuePublishAttempts } from "../api/queue.api";
import { getChannels } from "@/features/channels/api/channels.api";
import { getProducts } from "@/features/products/api/products.api";
import { setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) =>
    createElement("a", { href }, children),
}));

const navigationMock = vi.hoisted(() => ({
  searchParams: new URLSearchParams(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: navigationMock.replace }),
  useSearchParams: () => navigationMock.searchParams,
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
  getFacebookPages: vi.fn(async () => ({
    items: [],
    total: 0,
    skip: 0,
    limit: 20,
  })),
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
const getQueueItemMock = vi.mocked(getQueueItem);
const getQueuePublishAttemptsMock = vi.mocked(getQueuePublishAttempts);

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
});
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
  navigationMock.searchParams = new URLSearchParams();
  navigationMock.replace.mockReset();
  vi.clearAllMocks();
});

const DETAIL_ID = "11111111-1111-4111-8111-111111111111";

function queueItem(id = DETAIL_ID) {
  return {
    id,
    title: "منشور عميق الرابط",
    content: "محتوى اختباري",
    status: "published" as const,
    scheduled_at: null,
    published_at: "2026-11-18T10:00:00Z",
    provider: "telegram" as const,
    channel_id: null,
    facebook_page_id: null,
    product_id: null,
    image_url: null,
    button_text: null,
    button_url: null,
    telegram_message_id: null,
    created_at: "2026-11-18T09:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    last_attempt: null,
    failure_reason: null,
    retry_count: 0,
  };
}

function prepareDeepLinkTest(search = `item=${DETAIL_ID}`) {
  setActiveWorkspaceId(WORKSPACE_A);
  navigationMock.searchParams = new URLSearchParams(search);
  getChannelsMock.mockResolvedValue({
    items: [],
    total: 0,
    skip: 0,
    limit: 20,
  });
  getProductsMock.mockResolvedValue({
    items: [],
    total: 0,
    skip: 0,
    limit: 200,
  });
  getQueuePublishAttemptsMock.mockResolvedValue({
    queue_id: DETAIL_ID,
    items: [],
    total: 0,
  });
}

describe("QueueView workspace gating", () => {
  it("shows no-workspace state and does not fetch tenant queues", () => {
    getProductsMock.mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 200,
    });
    renderView();
    expect(screen.getByText("لا توجد مساحة عمل نشطة")).toBeInTheDocument();
    expect(getQueueMock).not.toHaveBeenCalled();
    expect(getChannelsMock).not.toHaveBeenCalled();
  });

  it("fetches GET /queues when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    getQueueMock.mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 200,
    });
    getChannelsMock.mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 20,
    });
    getProductsMock.mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 200,
    });

    renderView();
    await waitFor(() => expect(getQueueMock).toHaveBeenCalledTimes(1));
  });

  it("opens a deep-linked item from the loaded list without a detail request", async () => {
    prepareDeepLinkTest();
    const item = queueItem();
    getQueueMock.mockResolvedValue({
      items: [item],
      total: 1,
      skip: 0,
      limit: 200,
    });

    renderView();

    expect(
      await screen.findByRole("dialog", { name: "تفاصيل عملية النشر" }),
    ).toBeInTheDocument();
    expect(getQueueItemMock).not.toHaveBeenCalled();
  });

  it("fetches and opens a deep-linked item outside the loaded list", async () => {
    prepareDeepLinkTest();
    expect(navigationMock.searchParams.get("item")).toBe(DETAIL_ID);
    getQueueMock.mockResolvedValue({
      items: [],
      total: 201,
      skip: 0,
      limit: 200,
    });
    getQueueItemMock.mockResolvedValue(queueItem());

    renderView();

    await waitFor(() => expect(getQueueItemMock).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByRole("dialog", { name: "تفاصيل عملية النشر" }),
    ).toBeInTheDocument();
  });

  it("does not request invalid deep-link IDs and offers a safe return", async () => {
    prepareDeepLinkTest("item=not-a-queue-id");
    getQueueMock.mockResolvedValue({
      items: [],
      total: 0,
      skip: 0,
      limit: 200,
    });

    renderView();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "رابط عملية النشر غير صالح.",
    );
    expect(getQueueItemMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "عرض قائمة النشر" }),
    ).toBeInTheDocument();
  });

  it("handles an inaccessible deep-linked item without revealing provider details", async () => {
    prepareDeepLinkTest();
    getQueueMock.mockResolvedValue({
      items: [],
      total: 201,
      skip: 0,
      limit: 200,
    });
    getQueueItemMock.mockRejectedValue(new Error("workspace B secret"));

    renderView();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "تعذر فتح عملية النشر المطلوبة أو لم تعد متاحة.",
    );
    expect(screen.queryByText("workspace B secret")).not.toBeInTheDocument();
  });
});

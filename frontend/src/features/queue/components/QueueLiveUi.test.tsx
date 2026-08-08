import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import { createElement, useEffect, useState, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  queueAttemptsKey,
  queueKey,
  useQueuePublishAttempts,
  useQueueWorkspaceState,
} from "../hooks/useQueue";
import {
  createDebouncedQueueEventInvalidator,
  getQueryKeysForQueueEvent,
} from "../lib/queue-event-invalidation";
import { getQueueOperationalStats } from "../lib/operations";
import { QUEUE_EVENT_NAMES } from "../types/events";
import type { QueueItem } from "../types/api";
import { QueueOperationalStats } from "./QueueOperationalStats";

vi.mock("../api/queue.api", () => ({
  getQueuePublishAttempts: vi.fn(),
}));

import { getQueuePublishAttempts } from "../api/queue.api";

const getAttemptsMock = vi.mocked(getQueuePublishAttempts);

function makeItem(overrides: Partial<QueueItem> = {}): QueueItem {
  return {
    id: "q-1",
    title: "منشور",
    content: "محتوى",
    status: "queued",
    scheduled_at: null,
    published_at: null,
    channel_id: "ch-1",
    product_id: null,
    image_url: null,
    button_text: null,
    button_url: null,
    telegram_message_id: null,
    created_at: "2026-08-08T09:00:00.000Z",
    updated_at: "2026-08-08T09:00:00.000Z",
    last_attempt: null,
    failure_reason: null,
    retry_count: 0,
    ...overrides,
  };
}

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children);
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("F3 — QueueOperationalStats live updates from queue list data", () => {
  it("updates KPI cards when authoritative queue items change after refetch", () => {
    const initial = [
      makeItem({ id: "a", status: "queued" }),
      makeItem({
        id: "b",
        status: "scheduled",
        scheduled_at: "2026-08-09T09:00:00.000Z",
      }),
    ];
    const { rerender } = render(
      <QueueOperationalStats
        stats={getQueueOperationalStats(initial, new Set(), {})}
      />,
    );

    expect(screen.getByText("في الانتظار").parentElement).toHaveTextContent("1");
    expect(screen.getByText("مجدول").parentElement).toHaveTextContent("1");
    expect(screen.getByText("نُشر اليوم").parentElement).toHaveTextContent("0");

    const afterRefetch = [
      makeItem({
        id: "a",
        status: "published",
        published_at: new Date().toISOString(),
      }),
      makeItem({
        id: "b",
        status: "scheduled",
        scheduled_at: "2026-08-09T09:00:00.000Z",
      }),
    ];
    rerender(
      <QueueOperationalStats
        stats={getQueueOperationalStats(afterRefetch, new Set(), {})}
      />,
    );

    expect(screen.getByText("في الانتظار").parentElement).toHaveTextContent("0");
    expect(screen.getByText("مجدول").parentElement).toHaveTextContent("1");
    expect(screen.getByText("نُشر اليوم").parentElement).toHaveTextContent("1");
  });
});

describe("F3 — Queue list / selection after status change and deletion", () => {
  it("reflects status transitions from server list data and keeps filters working", async () => {
    const items = [
      makeItem({ id: "a", status: "queued", title: "صف واحد" }),
      makeItem({
        id: "b",
        status: "published",
        title: "منشور",
        published_at: "2026-08-08T10:00:00.000Z",
      }),
    ];

    const { result, rerender } = renderHook(
      ({ list }) => useQueueWorkspaceState(list),
      { initialProps: { list: items } },
    );

    act(() => {
      result.current.setStatusFilter("queued");
    });
    await waitFor(() => {
      expect(result.current.filteredItems.map((item) => item.id)).toEqual(["a"]);
    });

    const updated = [
      makeItem({
        id: "a",
        status: "published",
        title: "صف واحد",
        published_at: new Date().toISOString(),
      }),
      makeItem({
        id: "b",
        status: "published",
        title: "منشور",
        published_at: "2026-08-08T10:00:00.000Z",
      }),
    ];
    rerender({ list: updated });

    await waitFor(() => {
      expect(result.current.filteredItems).toEqual([]);
    });

    act(() => {
      result.current.setStatusFilter("published");
    });
    await waitFor(() => {
      expect(result.current.filteredItems.map((item) => item.id).sort()).toEqual([
        "a",
        "b",
      ]);
    });
  });

  it("removes deleted items from selection after list refetch", async () => {
    const items = [makeItem({ id: "a" }), makeItem({ id: "b" })];
    const { result, rerender } = renderHook(
      ({ list }) => useQueueWorkspaceState(list),
      { initialProps: { list: items } },
    );

    act(() => {
      result.current.toggle("a");
      result.current.toggle("b");
    });
    await waitFor(() => {
      expect(result.current.selectedQueueItemIds.sort()).toEqual(["a", "b"]);
    });

    rerender({ list: [makeItem({ id: "b" })] });
    await waitFor(() => {
      expect(result.current.selectedQueueItemIds).toEqual(["b"]);
    });
  });
});

describe("F3 — QueueDetailsDrawer attempt query behavior", () => {
  it("does not fetch attempts while the drawer query is disabled (closed)", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    getAttemptsMock.mockResolvedValue({
      queue_id: "q-1",
      items: [],
      total: 0,
    });

    renderHook(() => useQueuePublishAttempts("q-1", false), {
      wrapper: wrapper(client),
    });

    await waitFor(() => expect(getAttemptsMock).not.toHaveBeenCalled());
  });

  it("refetches active attempts query when attempt events invalidate the key", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    getAttemptsMock.mockResolvedValue({
      queue_id: "q-1",
      items: [
        {
          attempt_number: 1,
          status: "failed",
          provider: "telegram",
          occurred_at: "2026-08-08T10:00:00.000Z",
          error_code: "telegram_error",
          error_message: "timeout",
          provider_chat_id: null,
          provider_message_id: null,
        },
      ],
      total: 1,
    });

    const { result } = renderHook(() => useQueuePublishAttempts("q-1", true), {
      wrapper: wrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callsBefore = getAttemptsMock.mock.calls.length;
    expect(callsBefore).toBeGreaterThanOrEqual(1);

    const invalidator = createDebouncedQueueEventInvalidator(client, 0);
    invalidator.handle({
      event: QUEUE_EVENT_NAMES.ATTEMPT_FAILED,
      version: 1,
      id: "evt-1",
      occurred_at: "2026-08-08T10:01:00.000Z",
      workspace_id: null,
      queue_id: "q-1",
      data: {
        queue_id: "q-1",
        attempt_number: 2,
        error_code: "telegram_error",
        is_terminal: false,
      },
    });

    await waitFor(() =>
      expect(getAttemptsMock.mock.calls.length).toBeGreaterThan(callsBefore),
    );
    expect(
      getQueryKeysForQueueEvent({
        event: QUEUE_EVENT_NAMES.ATTEMPT_FAILED,
        version: 1,
        id: "evt-1",
        occurred_at: "2026-08-08T10:01:00.000Z",
        workspace_id: null,
        queue_id: "q-1",
        data: {},
      }),
    ).toEqual([queueKey, queueAttemptsKey("q-1")]);
    invalidator.dispose();
  });
});

describe("F3 — deleted open item closes inspector without client store", () => {
  it("clears activePostId when the item disappears from the authoritative list", async () => {
    function Harness({ items }: { items: QueueItem[] }) {
      const [activePostId, setActivePostId] = useState<string | null>("q-1");
      const activePost =
        activePostId
          ? (items.find((item) => item.id === activePostId) ?? null)
          : null;

      useEffect(() => {
        if (activePostId == null) return;
        if (!items.some((item) => item.id === activePostId)) {
          setActivePostId(null);
        }
      }, [activePostId, items]);

      return (
        <div>
          <span data-testid="open">{String(activePost != null)}</span>
          <span data-testid="id">{activePostId ?? "none"}</span>
        </div>
      );
    }

    const { rerender } = render(<Harness items={[makeItem({ id: "q-1" })]} />);
    expect(screen.getByTestId("open")).toHaveTextContent("true");
    expect(screen.getByTestId("id")).toHaveTextContent("q-1");

    rerender(<Harness items={[]} />);
    await waitFor(() => {
      expect(screen.getByTestId("open")).toHaveTextContent("false");
      expect(screen.getByTestId("id")).toHaveTextContent("none");
    });
  });
});

describe("F3 — mutation invalidation remains compatible with realtime keys", () => {
  it("uses the same queueKey surface as SSE invalidation", () => {
    const statusKeys = getQueryKeysForQueueEvent({
      event: QUEUE_EVENT_NAMES.STATUS_CHANGED,
      version: 1,
      id: "e1",
      occurred_at: "2026-08-08T10:00:00.000Z",
      workspace_id: null,
      queue_id: "q-1",
      data: {},
    });
    expect(statusKeys).toEqual([queueKey]);
  });
});

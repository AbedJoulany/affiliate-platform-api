import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { QueueItem } from "../types/api";
import { QueueTable } from "./QueueTable";

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => createElement("img", { alt }),
}));

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

function item(overrides: Partial<QueueItem> = {}): QueueItem {
  return {
    id: "q-failed",
    title: "منشور فاشل",
    content: "محتوى",
    status: "failed",
    scheduled_at: null,
    published_at: null,
    channel_id: "ch-1",
    product_id: null,
    image_url: null,
    button_text: "اشتري الآن",
    button_url: "https://s.click.aliexpress.com/e/_promo",
    telegram_message_id: null,
    created_at: "2026-09-07T09:00:00.000Z",
    updated_at: "2026-09-07T09:00:00.000Z",
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe("QueueTable failed status", () => {
  it("shows a failed badge and retries from the explicit action", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <QueueTable
        items={[item()]}
        selectedIds={[]}
        allSelected={false}
        density="comfortable"
        productsById={new Map()}
        channelsById={new Map()}
        publishingIds={new Set()}
        failures={{}}
        onToggle={vi.fn()}
        onToggleAll={vi.fn()}
        onView={vi.fn()}
        onOpenProduct={vi.fn()}
        onSchedule={vi.fn()}
        onPublish={vi.fn()}
        onRetry={onRetry}
        onOpenAi={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByText("فشل")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "إعادة المحاولة" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

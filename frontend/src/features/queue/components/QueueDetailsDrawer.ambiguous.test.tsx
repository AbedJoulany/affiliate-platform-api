import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FacebookPage } from "@/features/channels/types/api";
import type { QueueItem } from "../types/api";
import { QueueDetailsDrawer } from "./QueueDetailsDrawer";

const { useQueuePublishAttempts } = vi.hoisted(() => ({
  useQueuePublishAttempts: vi.fn(),
}));

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => createElement("img", { alt }),
}));

vi.mock("../hooks/useQueue", () => ({
  useQueuePublishAttempts,
}));

function item(): QueueItem {
  return {
    id: "queue-facebook-1",
    title: "منشور Facebook غير مؤكد",
    content: "محتوى اختباري",
    status: "failed",
    provider: "facebook",
    scheduled_at: null,
    published_at: null,
    channel_id: null,
    facebook_page_id: "page-1",
    product_id: null,
    image_url: null,
    button_text: "اقرأ المزيد",
    button_url: "https://example.test/affiliate",
    telegram_message_id: null,
    created_at: "2026-01-01T09:00:00.000Z",
    updated_at: "2026-01-01T09:00:00.000Z",
    last_attempt: {
      attempt_number: 1,
      status: "ambiguous",
      provider: "facebook",
      occurred_at: "2026-01-01T09:01:00.000Z",
      error_code: "provider_timeout",
      error_message: "The provider outcome is unknown.",
      provider_chat_id: null,
      provider_message_id: null,
      provider_message_ref: null,
    },
  };
}

const page: FacebookPage = {
  id: "page-1",
  workspace_id: "workspace-1",
  facebook_page_id: "123",
  page_name: "Test Page",
  token_expires_at: null,
  is_active: true,
  validation_status: "valid",
  last_validated_at: "2026-01-01T08:00:00.000Z",
  last_error: null,
  has_access_token: true,
  created_at: "2026-01-01T08:00:00.000Z",
  updated_at: "2026-01-01T08:00:00.000Z",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("QueueDetailsDrawer ambiguous Facebook attempts", () => {
  it("requires explicit confirmation before retrying", async () => {
    useQueuePublishAttempts.mockReturnValue({
      data: { items: [item().last_attempt], total: 1 },
      isPending: false,
      isError: false,
    });
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(
      <QueueDetailsDrawer
        item={item()}
        product={null}
        channel={null}
        facebookPage={page}
        publishing={false}
        open
        onClose={vi.fn()}
        onPublish={vi.fn()}
        onRetry={onRetry}
        onSchedule={vi.fn()}
        onOpenAi={vi.fn()}
      />,
    );

    expect(screen.getByText("نتيجة غير مؤكدة · راجع الصفحة")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "مراجعة وإعادة المحاولة" }));
    expect(onRetry).not.toHaveBeenCalled();
    expect(screen.getByRole("alertdialog")).toHaveTextContent("قد يكون Meta قد قبل المنشور بالفعل");

    await user.click(screen.getByRole("button", { name: "تأكيد إعادة المحاولة" }));
    expect(onRetry).toHaveBeenCalledWith(item(), { confirmAmbiguous: true });
  });
});

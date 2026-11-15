import { expect, test, type Page, type Request } from "@playwright/test";
import {
  QUEUE_ID,
  login,
  stubPixelImages,
  stubSession,
  stubQueueStream,
} from "./lib/session";

const FACEBOOK_PAGE_ROW_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const FACEBOOK_PAGE_ID = "1234567890";

const facebookPage = {
  id: FACEBOOK_PAGE_ROW_ID,
  workspace_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  facebook_page_id: FACEBOOK_PAGE_ID,
  page_name: "صفحة الاختبار",
  token_expires_at: null,
  is_active: true,
  validation_status: "valid",
  last_validated_at: "2026-07-16T00:00:00Z",
  last_error: null,
  has_access_token: true,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
};

function attempt(status: "failed" | "ambiguous") {
  return {
    attempt_number: 1,
    status,
    provider: "facebook",
    occurred_at: "2026-07-16T01:00:00Z",
    error_code:
      status === "ambiguous" ? "provider_timeout" : "provider_rejected",
    error_message:
      status === "ambiguous"
        ? "قد يكون المزود قد قبل الطلب."
        : "رفض المزود الطلب.",
    provider_chat_id: null,
    provider_message_id: null,
    provider_message_ref: null,
  };
}

function queueItem(
  status: "failed" | "queued" = "failed",
  latestAttempt = attempt("ambiguous"),
) {
  return {
    id: QUEUE_ID,
    title: "منشور Facebook اختباري",
    content: "محتوى اختباري",
    status,
    scheduled_at: null,
    published_at: null,
    provider: "facebook",
    channel_id: null,
    facebook_page_id: FACEBOOK_PAGE_ROW_ID,
    product_id: null,
    image_url: null,
    button_text: "اقرأ المزيد",
    button_url: "https://example.test/affiliate",
    telegram_message_id: null,
    created_at: "2026-07-16T00:00:00Z",
    updated_at: "2026-07-16T01:00:00Z",
    last_attempt: latestAttempt,
    failure_reason: latestAttempt?.error_message ?? null,
    retry_count: latestAttempt ? 1 : 0,
  };
}

async function stubFacebookQueue(
  page: Page,
  current: () => ReturnType<typeof queueItem>,
  onPublish: (request: Request) => void,
  rejectPublish = false,
  publishDelayMs = 0,
) {
  await stubPixelImages(page);
  await stubSession(page);
  await stubQueueStream(page);
  await page.route("**/api/v1/channels**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 20 } });
  });
  await page.route("**/api/v1/facebook/pages**", async (route) => {
    await route.fulfill({
      json: { items: [facebookPage], total: 1, skip: 0, limit: 20 },
    });
  });
  await page.route("**/api/v1/products**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 200 } });
  });
  await page.route("**/api/v1/queues**", async (route) => {
    const request = route.request();
    const url = request.url();
    if (url.includes("/stream")) {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    if (url.includes("/attempts")) {
      const item = current();
      await route.fulfill({
        json: {
          queue_id: QUEUE_ID,
          items: item.last_attempt ? [item.last_attempt] : [],
          total: item.last_attempt ? 1 : 0,
        },
      });
      return;
    }
    if (
      request.method() === "POST" &&
      url.endsWith(`/queues/${QUEUE_ID}/publish`)
    ) {
      onPublish(request);
      if (publishDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, publishDelayMs));
      }
      if (rejectPublish) {
        await route.fulfill({
          status: 409,
          json: { detail: "لا يمكن إعادة المحاولة حالياً." },
        });
        return;
      }
      await route.fulfill({
        json: {
          queue_id: QUEUE_ID,
          provider: "facebook",
          telegram_message_id: null,
          provider_message_ref: "facebook-post-1",
          chat_id: null,
          destination_id: FACEBOOK_PAGE_ID,
          message_type: "text",
          published_at: "2026-07-16T01:05:00Z",
        },
      });
      return;
    }
    if (request.method() === "PATCH" && url.endsWith(`/queues/${QUEUE_ID}`)) {
      await route.fulfill({ json: { ...current(), status: "queued" } });
      return;
    }
    await route.fulfill({
      json: { items: [current()], total: 1, skip: 0, limit: 200 },
    });
  });
}

test("shows an ambiguous Facebook attempt and cancellation sends no retry", async ({
  page,
}) => {
  let retryRequests = 0;
  await stubFacebookQueue(
    page,
    () => queueItem(),
    () => {
      retryRequests += 1;
    },
  );

  await login(page);
  await page.goto("/queue");
  await expect(page.getByText("Facebook • صفحة الاختبار")).toBeVisible();
  await expect(page.getByText("غير مؤكد")).toBeVisible();
  await page.getByRole("button", { name: "مراجعة النشر" }).click();
  await expect(page.getByText("نتيجة غير مؤكدة · راجع الصفحة")).toBeVisible();
  await page.getByRole("button", { name: "مراجعة وإعادة المحاولة" }).click();
  await expect(page.getByRole("alertdialog")).toContainText(
    "قد يكون Meta قد قبل المنشور بالفعل",
  );
  await page.getByRole("button", { name: "إلغاء" }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  expect(retryRequests).toBe(0);
});

test("sends one explicitly confirmed ambiguous retry with the confirmation query", async ({
  page,
}) => {
  let retryRequests = 0;
  let retryQuery: string | null = null;
  await stubFacebookQueue(
    page,
    () => queueItem(),
    (request) => {
      retryRequests += 1;
      retryQuery = new URL(request.url()).searchParams.get("confirm_ambiguous");
    },
    false,
    250,
  );

  await login(page);
  await page.goto("/queue");
  await page.getByRole("button", { name: "مراجعة النشر" }).click();
  await page.getByRole("button", { name: "مراجعة وإعادة المحاولة" }).click();
  await page.getByRole("button", { name: "تأكيد إعادة المحاولة" }).click();
  await expect(
    page.getByRole("button", { name: "مراجعة وإعادة المحاولة" }),
  ).toBeDisabled();
  await expect(page.getByText(/تم نشر .* منشور بنجاح/)).toBeVisible();
  expect(retryRequests).toBe(1);
  expect(retryQuery).toBe("true");
});

test("ordinary Facebook failures use the standard retry without confirmation", async ({
  page,
}) => {
  let retryQuery: string | null = "unexpected";
  await stubFacebookQueue(
    page,
    () => queueItem("failed", attempt("failed")),
    (request) => {
      retryQuery = new URL(request.url()).searchParams.get("confirm_ambiguous");
    },
  );

  await login(page);
  await page.goto("/queue");
  await page.getByRole("button", { name: "إعادة المحاولة" }).click();
  await expect(page.getByText(/تم نشر .* منشور بنجاح/)).toBeVisible();
  expect(retryQuery).toBeNull();
});

test("keeps a backend retry rejection as an error", async ({ page }) => {
  let retryRequests = 0;
  await stubFacebookQueue(
    page,
    () => queueItem(),
    () => {
      retryRequests += 1;
    },
    true,
  );

  await login(page);
  await page.goto("/queue");
  await page.getByRole("button", { name: "مراجعة النشر" }).click();
  await page.getByRole("button", { name: "مراجعة وإعادة المحاولة" }).click();
  await page.getByRole("button", { name: "تأكيد إعادة المحاولة" }).click();
  await expect(page.getByText("لا يمكن إعادة المحاولة حالياً.")).toBeVisible();
  expect(retryRequests).toBe(1);
  await expect(page.getByText("تم نشر 1 منشور بنجاح.")).toHaveCount(0);
});

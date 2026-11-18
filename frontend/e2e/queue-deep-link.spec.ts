import { expect, test } from "@playwright/test";
import {
  QUEUE_ID,
  login,
  stubPixelImages,
  stubQueueStream,
  stubSession,
} from "./lib/session";

const deepLinkedItem = {
  id: QUEUE_ID,
  title: "منشور خارج الصفحة الأولى",
  content: "محتوى عملية النشر المرتبطة مباشرة",
  status: "published",
  scheduled_at: null,
  published_at: "2026-11-18T10:00:00Z",
  provider: "telegram",
  channel_id: null,
  facebook_page_id: null,
  product_id: null,
  image_url: null,
  button_text: null,
  button_url: null,
  telegram_message_id: "telegram-message-1",
  created_at: "2026-11-18T09:00:00Z",
  updated_at: "2026-11-18T10:00:00Z",
  last_attempt: null,
  failure_reason: null,
  retry_count: 0,
};

test("opens a queue item outside the first page from a deep link", async ({
  page,
}) => {
  await stubPixelImages(page);
  await stubSession(page);
  await stubQueueStream(page);

  await page.route("**/api/v1/channels**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 20 } });
  });
  await page.route("**/api/v1/facebook/pages**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 20 } });
  });
  await page.route("**/api/v1/products**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 200 } });
  });
  await page.route("**/api/v1/queues**", async (route) => {
    const url = route.request().url();
    if (url.includes("/attempts")) {
      await route.fulfill({
        json: { queue_id: QUEUE_ID, items: [], total: 0 },
      });
      return;
    }
    if (
      route.request().method() === "GET" &&
      url.endsWith(`/queues/${QUEUE_ID}`)
    ) {
      await route.fulfill({ json: deepLinkedItem });
      return;
    }
    await route.fulfill({
      json: { items: [], total: 201, skip: 0, limit: 200 },
    });
  });

  await login(page);
  await page.goto(`/queue?item=${QUEUE_ID}`);

  await expect(
    page.getByRole("dialog", { name: "تفاصيل عملية النشر" }),
  ).toBeVisible();
  await expect(page.getByText("منشور خارج الصفحة الأولى")).toBeVisible();
});

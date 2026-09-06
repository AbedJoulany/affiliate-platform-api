import { expect, test, type Page } from "@playwright/test";
import {
  CHANNEL_ID,
  PRODUCT_ID,
  QUEUE_ID,
  catalogProduct,
  channelBody,
  discoveryResponse,
  header,
  login,
  queueItem,
  stubPixelImages,
  stubQueueStream,
  stubSession,
} from "./lib/session";

test("import product from discovery without a workspace header", async ({ page }) => {
  let importHeader: string | null = "unset";
  let importPosted = false;

  await stubPixelImages(page);
  await stubSession(page);
  await page.route("**/api/v1/aliexpress/categories", async (route) => {
    await route.fulfill({ json: { items: [] } });
  });
  await page.route("**/api/v1/products**", async (route) => {
    const request = route.request();
    const url = request.url();
    if (request.method() === "POST" && url.includes("/products/import")) {
      importPosted = true;
      importHeader = header(request, "X-Workspace-Id");
      expect(JSON.parse(request.postData() ?? "{}")).toEqual({ product_id: "100500" });
      await route.fulfill({
        status: 201,
        json: {
          imported: true,
          aliexpress_product_id: "100500",
          image_count: 1,
          product: catalogProduct,
        },
      });
      return;
    }
    if (request.method() === "GET" && url.includes("/products/discover")) {
      await route.fulfill({ json: discoveryResponse });
      return;
    }
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 25 } });
  });

  await login(page);
  await page.goto("/discovery");
  await expect(page.getByRole("heading", { name: "اكتشاف المنتجات", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "تشغيل الاكتشاف" }).first().click();
  await expect(page.getByText("Wireless Earbuds")).toBeVisible();
  await page.getByRole("button", { name: "استيراد" }).click();
  await expect(page.getByText("تم استيراد: Wireless Earbuds")).toBeVisible();
  expect(importPosted).toBe(true);
  expect(importHeader).toBeNull();
});

test("generate marketing content from a catalog product", async ({ page }) => {
  let generatePosted = false;

  await stubPixelImages(page);
  await stubSession(page);
  await page.route("**/api/v1/products**", async (route) => {
    await route.fulfill({
      json: { items: [catalogProduct], total: 1, skip: 0, limit: 20 },
    });
  });
  await page.route("**/api/v1/ai-content/generate", async (route) => {
    generatePosted = true;
    expect(route.request().method()).toBe("POST");
    const body = JSON.parse(route.request().postData() ?? "{}") as { product_id?: string };
    expect(body.product_id).toBe(PRODUCT_ID);
    await route.fulfill({
      json: {
        product_id: PRODUCT_ID,
        source_url: null,
        provider: "openai",
        content: "عنوان تجريبي\n\nنص تسويقي جاهز للنشر.",
        content_type: "telegram",
        tone: "persuasive",
        language: "ar",
        length: "medium",
      },
    });
  });

  await login(page);
  await page.goto(`/ai?product=${PRODUCT_ID}`);
  await expect(page.getByRole("heading", { name: "مساحة محتوى التسويق" })).toBeVisible();
  await page.getByRole("button", { name: "إنشاء المحتوى" }).click();
  await expect(page.getByText("تم إنشاء النسخة الأولى.")).toBeVisible();
  expect(generatePosted).toBe(true);
});

async function stubQueueWorkspace(page: Page, current: () => ReturnType<typeof queueItem>) {
  await stubPixelImages(page);
  await stubSession(page);
  await stubQueueStream(page);
  await page.route("**/api/v1/channels**", async (route) => {
    await route.fulfill({ json: { items: [channelBody], total: 1, skip: 0, limit: 20 } });
  });
  await page.route("**/api/v1/products**", async (route) => {
    await route.fulfill({
      json: { items: [catalogProduct], total: 1, skip: 0, limit: 200 },
    });
  });
  await page.route("**/api/v1/queues**", async (route) => {
    const request = route.request();
    const url = request.url();
    const item = current();
    if (url.includes("/stream")) {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    if (url.includes("/attempts")) {
      await route.fulfill({ json: { queue_id: QUEUE_ID, items: [], total: 0 } });
      return;
    }
    if (request.method() === "GET" && url.includes(`/queues/${QUEUE_ID}`)) {
      await route.fulfill({ json: item });
      return;
    }
    await route.fulfill({ json: { items: [item], total: 1, skip: 0, limit: 200 } });
  });
}

test("publish a queued item now", async ({ page }) => {
  let current = queueItem();
  let published = false;

  await stubQueueWorkspace(page, () => current);
  await page.route("**/api/v1/queues/**/publish", async (route) => {
    published = true;
    current = queueItem({
      status: "published",
      published_at: "2026-07-16T01:00:00Z",
      telegram_message_id: 42,
    });
    await route.fulfill({
      json: {
        queue_id: QUEUE_ID,
        telegram_message_id: 42,
        chat_id: "@ops",
        message_type: "text",
        published_at: "2026-07-16T01:00:00Z",
      },
    });
  });

  await login(page);
  await page.goto("/queue");
  await expect(page.getByRole("heading", { name: "مركز عمليات النشر" })).toBeVisible();
  await expect(page.getByText("Wireless Earbuds")).toBeVisible();
  await page.getByRole("button", { name: "نشر الآن" }).click();
  await expect(page.getByText(/تم نشر .* منشور بنجاح/)).toBeVisible();
  expect(published).toBe(true);
});

test("schedule a queued item for later", async ({ page }) => {
  let current = queueItem();
  let patched = false;

  await stubQueueWorkspace(page, () => current);
  await page.route(`**/api/v1/queues/${QUEUE_ID}`, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.fulfill({ json: current });
      return;
    }
    patched = true;
    const body = JSON.parse(route.request().postData() ?? "{}") as {
      channel_id?: string;
      status?: string;
      scheduled_at?: string;
    };
    expect(body.channel_id).toBe(CHANNEL_ID);
    expect(body.status).toBe("scheduled");
    expect(body.scheduled_at).toBeTruthy();
    current = queueItem({
      status: "scheduled",
      scheduled_at: body.scheduled_at,
      channel_id: body.channel_id,
    });
    await route.fulfill({ json: current });
  });

  await login(page);
  await page.goto("/queue");
  await expect(page.getByRole("heading", { name: "مركز عمليات النشر" })).toBeVisible();
  await page.getByRole("button", { name: "غير مجدول" }).click();
  await expect(page.getByRole("heading", { name: "إعداد عملية النشر" })).toBeVisible();
  await page.getByRole("button", { name: "بعد ساعة" }).click();
  await page.getByRole("button", { name: "حفظ الجدولة" }).click();
  await expect(page.getByText("تم تحديث موعد النشر.")).toBeVisible();
  expect(patched).toBe(true);
});

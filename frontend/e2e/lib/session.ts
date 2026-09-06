import { expect, type Page, type Request } from "@playwright/test";

export const WORKSPACE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
export const USER_ID = "00000000-0000-0000-0000-000000000001";
export const PRODUCT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
export const QUEUE_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
export const CHANNEL_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

export const meBody = {
  id: USER_ID,
  email: "owner@example.com",
  full_name: "مالك المنصة",
  role: "admin",
  is_active: true,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
  default_workspace_id: WORKSPACE_ID,
};

export const dashboardBody = {
  products: {
    total: 24,
    by_status: { draft: 2, active: 20, inactive: 1, archived: 1 },
  },
  queue: {
    total: 6,
    by_status: { draft: 1, queued: 2, scheduled: 3, published: 0 },
  },
  channels: { total: 3, active: 2, inactive: 1 },
  recent_activity: [],
  system_status: {
    status: "operational",
    database: "up",
    generated_at: "2026-07-16T00:00:00Z",
  },
};

export const catalogProduct = {
  id: PRODUCT_ID,
  aliexpress_product_id: "100500",
  title: "Wireless Earbuds",
  description: null,
  price: 29.99,
  original_price: 49.99,
  discount: 40,
  rating: 4.8,
  sales: 1500,
  reviews: 120,
  image_url: "https://example.com/main.jpg",
  gallery_images: ["https://example.com/main.jpg"],
  product_url: "https://www.aliexpress.com/item/100500.html",
  affiliate_url: null,
  category: null,
  store_name: null,
  currency: "USD",
  commission_rate: 8,
  shipping_info: null,
  score: 82,
  status: "active",
  last_synced_at: null,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
};

export const discoveryItem = {
  aliexpress_product_id: "100500",
  title: "Wireless Earbuds",
  description: null,
  price: 29.99,
  original_price: 49.99,
  discount: 40,
  rating: 4.8,
  sales: 1500,
  reviews: 120,
  image_url: "https://example.com/main.jpg",
  gallery_images: ["https://example.com/main.jpg"],
  product_url: "https://www.aliexpress.com/item/100500.html",
  affiliate_url: null,
  category: null,
  store_name: null,
  currency: "USD",
  commission_rate: 8,
  shipping_info: null,
  score: 82,
};

export const discoveryResponse = {
  items: [discoveryItem],
  total: 1,
  skip: 0,
  limit: 20,
  page: 1,
  total_pages: 1,
  mode: "hot",
  sort: "orders_desc",
  persisted_count: 0,
};

export const channelBody = {
  id: CHANNEL_ID,
  telegram_channel_id: "@ops",
  title: "قناة النشر",
  username: "ops",
  bot_permission_status: "granted",
  can_post_messages: true,
  can_edit_messages: true,
  can_delete_messages: true,
  permissions_checked_at: "2026-07-16T00:00:00Z",
  permission_detail: null,
  is_active: true,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
};

export function queueItem(overrides: Record<string, unknown> = {}) {
  return {
    id: QUEUE_ID,
    title: "Wireless Earbuds",
    content: "نص جاهز للنشر",
    status: "draft",
    scheduled_at: null,
    published_at: null,
    channel_id: CHANNEL_ID,
    product_id: PRODUCT_ID,
    image_url: null,
    button_text: null,
    button_url: null,
    telegram_message_id: null,
    created_at: "2026-07-16T00:00:00Z",
    updated_at: "2026-07-16T00:00:00Z",
    last_attempt: null,
    failure_reason: null,
    retry_count: 0,
    ...overrides,
  };
}

export function header(request: Request, name: string): string | null {
  return request.headers()[name.toLowerCase()] ?? null;
}

export async function stubPixelImages(page: Page) {
  await page.route("https://example.com/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      body: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "base64",
      ),
    });
  });
}

export async function stubSession(page: Page) {
  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      json: {
        access_token: "fixture-token",
        token_type: "bearer",
        refresh_token: "fixture-refresh-token",
      },
    });
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({ json: meBody });
  });
  await page.route("**/api/v1/dashboard", async (route) => {
    await route.fulfill({ json: dashboardBody });
  });
}

export async function login(page: Page) {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "مرحبًا بعودتك" })).toBeVisible();
  await page.getByLabel("البريد الإلكتروني").fill("owner@example.com");
  await page.getByLabel("كلمة المرور").fill("password123");
  await page.getByRole("button", { name: "تسجيل الدخول" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

export async function stubQueueStream(page: Page) {
  await page.route("**/api/v1/queues/stream**", async (route) => {
    await route.fulfill({ status: 204, body: "" });
  });
}

import { expect, test, type Page, type Request } from "@playwright/test";

const WORKSPACE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

const meBody = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "owner@example.com",
  full_name: "مالك المنصة",
  role: "admin",
  is_active: true,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
  default_workspace_id: WORKSPACE_ID,
};

const dashboardBody = {
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

const imageSearchItem = {
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
  gallery_images: ["https://example.com/main.jpg", "https://example.com/alt.jpg"],
  product_url: "https://www.aliexpress.com/item/100500.html",
  affiliate_url: null,
  category: null,
  store_name: null,
  currency: "USD",
  commission_rate: 8,
  shipping_info: null,
  score: 82,
};

function header(request: Request, name: string): string | null {
  return request.headers()[name.toLowerCase()] ?? null;
}

async function login(page: Page) {
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
  await page.goto("/login");
  await page.getByLabel("البريد الإلكتروني").fill("owner@example.com");
  await page.getByLabel("كلمة المرور").fill("password123");
  await page.getByRole("button", { name: "تسجيل الدخول" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("image search is global and tenant pages still send X-Workspace-Id", async ({ page }) => {
  let imageSearchHeader: string | null = "unset";
  let dashboardHeader: string | null = "unset";

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
    dashboardHeader = header(route.request(), "X-Workspace-Id");
    await route.fulfill({ json: dashboardBody });
  });
  await page.route("**/api/v1/aliexpress/categories", async (route) => {
    await route.fulfill({ json: { items: [] } });
  });
  await page.route("**/api/v1/products**", async (route) => {
    const request = route.request();
    if (request.url().includes("/products/search/image")) {
      imageSearchHeader = header(request, "X-Workspace-Id");
      expect(request.method()).toBe("POST");
      await route.fulfill({
        json: {
          items: [imageSearchItem],
          total: 1,
          skip: 0,
          limit: 20,
          page: 1,
          total_pages: 1,
          mode: "general",
          sort: "orders_desc",
          persisted_count: 0,
        },
      });
      return;
    }
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 25 } });
  });

  await login(page);
  await expect(page.getByRole("heading", { name: "لوحة التحكم" })).toBeVisible();
  expect(dashboardHeader).toBe(WORKSPACE_ID);

  await page.goto("/discovery");
  await expect(page.getByRole("heading", { name: "اكتشاف المنتجات", exact: true })).toBeVisible();

  await page.getByLabel("رابط الصورة").fill("https://example.com/product.jpg");
  await page.getByRole("button", { name: "بحث بالصورة" }).click();

  await expect(page.getByText("Wireless Earbuds")).toBeVisible();
  await page.getByRole("button", { name: "معاينة" }).click();
  await expect(page.getByRole("heading", { name: "معاينة المنتج" })).toBeVisible();
  await page.getByLabel("اختيار صورة المنتج").nth(1).click();
  await expect(page.getByLabel("اختيار صورة المنتج").nth(1)).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  expect(imageSearchHeader).toBeNull();
});

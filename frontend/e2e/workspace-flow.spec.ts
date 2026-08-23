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

async function fulfillJson(page: Page, glob: string, body: unknown, status = 200) {
  await page.route(glob, async (route) => {
    await route.fulfill({ status, json: body });
  });
}

function header(request: Request, name: string): string | null {
  return request.headers()[name.toLowerCase()] ?? null;
}

test("login restores default_workspace_id and loads tenant pages with X-Workspace-Id", async ({
  page,
}) => {
  const tenantHeaders: Record<string, string | null> = {};
  const productHeaders: string[] = [];

  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      json: {
        access_token: "fixture-token",
        token_type: "bearer",
        refresh_token: "fixture-refresh-token",
      },
    });
  });
  await fulfillJson(page, "**/api/v1/auth/me", meBody);
  await page.route("**/api/v1/dashboard", async (route) => {
    tenantHeaders.dashboard = header(route.request(), "X-Workspace-Id");
    await route.fulfill({ json: dashboardBody });
  });
  await page.route("**/api/v1/queues**", async (route) => {
    if (route.request().url().includes("/stream")) {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    tenantHeaders.queues = header(route.request(), "X-Workspace-Id");
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 200 } });
  });
  await page.route("**/api/v1/channels**", async (route) => {
    tenantHeaders.channels = header(route.request(), "X-Workspace-Id");
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 20 } });
  });
  await page.route("**/api/v1/products**", async (route) => {
    const request = route.request();
    if (request.method() === "POST" && request.url().includes("/import")) {
      expect(header(request, "X-Workspace-Id")).toBeNull();
      await route.fulfill({
        status: 201,
        json: {
          imported: true,
          aliexpress_product_id: "100500",
          product: { id: "p-1", title: "Imported" },
        },
      });
      return;
    }
    productHeaders.push(header(request, "X-Workspace-Id") ?? "");
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 25 } });
  });

  await page.goto("/login");
  await page.getByLabel("البريد الإلكتروني").fill("owner@example.com");
  await page.getByLabel("كلمة المرور").fill("password123");
  await page.getByRole("button", { name: "تسجيل الدخول" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "لوحة التحكم" })).toBeVisible();
  await expect(page.getByText("24", { exact: true })).toBeVisible();
  expect(tenantHeaders.dashboard).toBe(WORKSPACE_ID);
  expect(
    await page.evaluate(() => window.sessionStorage.getItem("affiliate_active_workspace_id")),
  ).toBe(WORKSPACE_ID);

  await page.goto("/queue");
  await expect(page.getByRole("heading", { name: "مركز عمليات النشر" })).toBeVisible();
  await expect(page.getByText("لا توجد مساحة عمل نشطة")).toHaveCount(0);
  expect(tenantHeaders.queues).toBe(WORKSPACE_ID);

  await page.goto("/channels");
  await expect(page.getByRole("heading", { name: "قنوات Telegram" })).toBeVisible();
  expect(tenantHeaders.channels).toBe(WORKSPACE_ID);

  await page.goto("/products");
  await expect(page.getByText("لا توجد مساحة عمل نشطة")).toHaveCount(0);
  expect(productHeaders.every((value) => value === "")).toBe(true);
});

test("no default workspace shows an explicit empty state instead of infinite loading", async ({
  page,
}) => {
  let dashboardCalled = false;
  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      json: {
        access_token: "fixture-token",
        token_type: "bearer",
        refresh_token: "fixture-refresh-token",
      },
    });
  });
  await fulfillJson(page, "**/api/v1/auth/me", { ...meBody, default_workspace_id: null });
  await page.route("**/api/v1/dashboard", async (route) => {
    dashboardCalled = true;
    await route.fulfill({ json: dashboardBody });
  });
  await page.route("**/api/v1/products**", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 25 } });
  });

  await page.goto("/login");
  await page.getByLabel("البريد الإلكتروني").fill("owner@example.com");
  await page.getByLabel("كلمة المرور").fill("password123");
  await page.getByRole("button", { name: "تسجيل الدخول" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("لا توجد مساحة عمل نشطة")).toBeVisible();
  expect(dashboardCalled).toBe(false);
});

test("stale workspace header for a non-member shows an error, not infinite loading", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.sessionStorage.setItem(
      "affiliate_active_workspace_id",
      "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    );
  });
  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      json: {
        access_token: "fixture-token",
        token_type: "bearer",
        refresh_token: "fixture-refresh-token",
      },
    });
  });
  await fulfillJson(page, "**/api/v1/auth/me", {
    ...meBody,
    role: "affiliate",
    default_workspace_id: null,
  });
  await page.route("**/api/v1/dashboard", async (route) => {
    await route.fulfill({
      status: 403,
      json: { detail: "Insufficient permissions" },
    });
  });

  await page.goto("/login");
  await page.getByLabel("البريد الإلكتروني").fill("user@example.com");
  await page.getByLabel("كلمة المرور").fill("password123");
  await page.getByRole("button", { name: "تسجيل الدخول" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("Insufficient permissions")).toBeVisible();
  await expect(page.getByLabel("جار التحميل")).toHaveCount(0);
});

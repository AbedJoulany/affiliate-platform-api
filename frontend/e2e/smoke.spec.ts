import { expect, test } from "@playwright/test";

test("logs in and renders typed dashboard fixture", async ({ page }) => {
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
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      json: {
        id: "00000000-0000-0000-0000-000000000001",
        email: "owner@example.com",
        full_name: "مالك المنصة",
        role: "admin",
        is_active: true,
        created_at: "2026-07-16T00:00:00Z",
        updated_at: "2026-07-16T00:00:00Z",
      },
    });
  });
  await page.route("**/api/v1/dashboard", async (route) => {
    await route.fulfill({
      json: {
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
      },
    });
  });

  await page.goto("/login");
  await page.getByLabel("البريد الإلكتروني").fill("owner@example.com");
  await page.getByLabel("كلمة المرور").fill("password123");
  await page.getByRole("button", { name: "تسجيل الدخول" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "لوحة التحكم" })).toBeVisible();
  await expect(page.getByText("24", { exact: true })).toBeVisible();
});

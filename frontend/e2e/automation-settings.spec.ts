import { expect, test } from "@playwright/test";
import { login, stubQueueStream, stubSession, WORKSPACE_ID, CHANNEL_ID } from "./lib/session";

const policy = {
  id: null,
  workspace_id: WORKSPACE_ID,
  revision: 0,
  enabled: false,
  configuration_ready: false,
  execution_available: false,
  execution_state: "disabled",
  destination: null,
  discovery: { keywords: null, min_price: null, max_price: null, min_rating: null, min_orders: null, min_discount: null, min_commission: null, max_commission: null, products_per_run: 5 },
  schedule: { frequency: "daily", preferred_time_local: "09:00", timezone: "UTC", posts_per_day: 1 },
  content: { ai_provider: null, language: null, tone: null, content_type: null, length: null },
  warnings: [],
  created_at: null,
  updated_at: null,
};

test("loads automation settings and saves configuration only", async ({ page }) => {
  await stubSession(page);
  await stubQueueStream(page);
  await page.route("**/api/v1/workspace-settings", async (route) => {
    await route.fulfill({ json: { can_edit: true, timezone: "UTC" } });
  });
  await page.route("**/api/v1/channels", async (route) => {
    await route.fulfill({ json: { items: [{ id: CHANNEL_ID, title: "قناة الاختبار", username: "test", telegram_channel_id: "@test", bot_permission_status: "granted", can_post_messages: true, is_active: true }], total: 1, skip: 0, limit: 50 } });
  });
  await page.route("**/api/v1/facebook/pages", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, skip: 0, limit: 50 } });
  });
  await page.route("**/api/v1/automation/config", async (route) => {
    if (route.request().method() === "PATCH") {
      const request = route.request().postDataJSON();
      expect(request.expected_revision).toBe(0);
      expect(request.discovery.keywords).toBe("سماعات");
      await route.fulfill({ json: { ...policy, discovery: { ...policy.discovery, keywords: "سماعات" } } });
      return;
    }
    await route.fulfill({ json: policy });
  });
  await login(page);
  await page.goto("/automation/settings");
  await expect(page.getByRole("heading", { name: "إعدادات الأتمتة" })).toBeVisible();
  await expect(page.getByText("التشغيل التلقائي غير متاح بعد")).toBeVisible();
  await page.getByLabel("الكلمات المفتاحية").fill("سماعات");
  await page.getByRole("button", { name: "حفظ التغييرات" }).click();
  await expect(page.getByText("تم حفظ إعدادات الأتمتة.")).toBeVisible();
});

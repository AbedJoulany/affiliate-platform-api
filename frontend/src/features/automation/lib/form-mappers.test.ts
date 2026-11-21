import { describe, expect, it } from "vitest";
import { buildAutomationPatch, toAutomationFormValues } from "./form-mappers";
import type { AutomationPolicy } from "../types/api";

const policy: AutomationPolicy = {
  id: "11111111-1111-4111-8111-111111111111",
  workspace_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  revision: 4,
  enabled: false,
  configuration_ready: false,
  execution_available: false,
  execution_state: "disabled",
  destination: null,
  discovery: {
    keywords: null,
    min_price: null,
    max_price: null,
    min_rating: null,
    min_orders: null,
    min_discount: null,
    min_commission: null,
    max_commission: null,
    products_per_run: 5,
  },
  schedule: {
    frequency: "daily",
    preferred_time_local: "09:00",
    timezone: "Asia/Jerusalem",
    posts_per_day: 1,
  },
  content: {
    ai_provider: null,
    language: null,
    tone: null,
    content_type: null,
    length: null,
  },
  warnings: ["Select an active, eligible destination"],
  created_at: null,
  updated_at: null,
};

describe("automation policy form mappers", () => {
  it("keeps a virtual policy at revision zero without inventing a destination", () => {
    const values = toAutomationFormValues({ ...policy, id: null, revision: 0 });
    expect(values.destination_provider).toBe("");
    expect(values.destination_id).toBe("");
    expect(buildAutomationPatch(values, { ...policy, id: null, revision: 0 })).toEqual({
      expected_revision: 0,
    });
  });

  it("sends only changed sections and preserves nullable inheritance", () => {
    const values = toAutomationFormValues(policy);
    values.destination_provider = "facebook";
    values.destination_id = "22222222-2222-4222-8222-222222222222";
    values.min_price = "12.50";
    values.ai_provider = "";
    values.language = "ar";

    expect(buildAutomationPatch(values, policy)).toEqual({
      expected_revision: 4,
      destination: {
        provider: "facebook",
        page_id: "22222222-2222-4222-8222-222222222222",
      },
      discovery: { min_price: "12.50" },
      content: { language: "ar" },
    });
  });

  it("clears a selected destination explicitly instead of falling back to Telegram", () => {
    const selected = {
      ...policy,
      destination: {
        provider: "telegram" as const,
        channel_id: "33333333-3333-4333-8333-333333333333",
        page_id: null,
        label: "قناة الاختبار",
        active: true,
        ready: true,
        status: "ready" as const,
      },
    };
    const values = toAutomationFormValues(selected);
    values.destination_provider = "";
    values.destination_id = "";
    expect(buildAutomationPatch(values, selected).destination).toBeNull();
  });
});

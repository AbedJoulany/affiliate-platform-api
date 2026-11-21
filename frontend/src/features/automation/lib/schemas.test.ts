import { describe, expect, it } from "vitest";
import { automationFormSchema } from "./schemas";

const validDraft = {
  enabled: false,
  destination_provider: "" as const,
  destination_id: "",
  keywords: "",
  min_price: "",
  max_price: "",
  min_rating: "",
  min_orders: "",
  min_discount: "",
  min_commission: "",
  max_commission: "",
  products_per_run: 5,
  frequency: "daily" as const,
  preferred_time_local: "09:00",
  posts_per_day: 1,
  ai_provider: "" as const,
  language: "" as const,
  tone: "" as const,
  content_type: "" as const,
  length: "" as const,
};

describe("automation form destination validation", () => {
  it("allows a disabled incomplete draft without sending a provider union", () => {
    const result = automationFormSchema.safeParse({
      ...validDraft,
      destination_provider: "facebook",
    });

    expect(result.success).toBe(true);
  });

  it("requires a destination before enabling the saved preference", () => {
    const result = automationFormSchema.safeParse({
      ...validDraft,
      enabled: true,
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            path: ["destination_id"],
            message: "اختر وجهة نشر صالحة قبل تفعيل الرغبة في الأتمتة",
          }),
        ]),
      );
    }
  });

  it("does not accept a provider without a destination when enabled", () => {
    const result = automationFormSchema.safeParse({
      ...validDraft,
      enabled: true,
      destination_provider: "telegram",
    });

    expect(result.success).toBe(false);
  });
});

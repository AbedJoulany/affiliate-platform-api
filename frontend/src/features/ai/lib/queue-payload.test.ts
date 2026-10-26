import { describe, expect, it } from "vitest";
import {
  DEFAULT_AFFILIATE_BUTTON_TEXT,
  buildAiQueueCreateInput,
  resolveAffiliateCta,
} from "./queue-payload";

describe("resolveAffiliateCta", () => {
  it("uses the affiliate URL and default button text", () => {
    expect(resolveAffiliateCta("https://s.click.aliexpress.com/e/_promo")).toEqual({
      button_text: DEFAULT_AFFILIATE_BUTTON_TEXT,
      button_url: "https://s.click.aliexpress.com/e/_promo",
    });
  });

  it("omits the CTA when there is no affiliate URL", () => {
    expect(resolveAffiliateCta(null)).toEqual({});
    expect(resolveAffiliateCta(undefined)).toEqual({});
  });
});

describe("buildAiQueueCreateInput", () => {
  it("sends channel, image, product, and affiliate CTA with the queue payload", () => {
    expect(
      buildAiQueueCreateInput({
        content: "منشور تسويقي",
        status: "queued",
        productId: "11111111-1111-4111-8111-111111111111",
        title: "سماعة",
        channelId: "22222222-2222-4222-8222-222222222222",
        imageUrl: "https://example.com/gadget.png",
        affiliateUrl: "https://s.click.aliexpress.com/e/_promo",
      }),
    ).toEqual({
      content: "منشور تسويقي",
      status: "queued",
      product_id: "11111111-1111-4111-8111-111111111111",
      title: "سماعة",
      channel_id: "22222222-2222-4222-8222-222222222222",
      image_url: "https://example.com/gadget.png",
      button_text: DEFAULT_AFFILIATE_BUTTON_TEXT,
      button_url: "https://s.click.aliexpress.com/e/_promo",
    });
  });

  it("does not invent a product_url CTA when affiliate URL is missing", () => {
    const payload = buildAiQueueCreateInput({
      content: "بدون عمولة",
      status: "draft",
      productId: "11111111-1111-4111-8111-111111111111",
    });

    expect(payload.button_url).toBeUndefined();
    expect(payload.button_text).toBeUndefined();
    expect(JSON.stringify(payload)).not.toContain("product_url");
  });
});

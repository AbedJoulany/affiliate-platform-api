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
  it("sends a Telegram destination, image, product, and affiliate CTA", () => {
    expect(
      buildAiQueueCreateInput({
        content: "منشور تسويقي",
        status: "queued",
        productId: "11111111-1111-4111-8111-111111111111",
        title: "سماعة",
        provider: "telegram",
        channelId: "22222222-2222-4222-8222-222222222222",
        imageUrl: "https://example.com/gadget.png",
        affiliateUrl: "https://s.click.aliexpress.com/e/_promo",
      }),
    ).toEqual({
      content: "منشور تسويقي",
      status: "queued",
      product_id: "11111111-1111-4111-8111-111111111111",
      title: "سماعة",
      provider: "telegram",
      channel_id: "22222222-2222-4222-8222-222222222222",
      image_url: "https://example.com/gadget.png",
      button_text: DEFAULT_AFFILIATE_BUTTON_TEXT,
      button_url: "https://s.click.aliexpress.com/e/_promo",
    });
  });

  it("sends a Facebook Page destination without a Telegram channel", () => {
    const payload = buildAiQueueCreateInput({
      content: "منشور Facebook",
      status: "queued",
      provider: "facebook",
      channelId: "should-not-be-sent",
      facebookPageId: "33333333-3333-4333-8333-333333333333",
      affiliateUrl: "https://s.click.aliexpress.com/e/_promo",
    });

    expect(payload).toMatchObject({
      provider: "facebook",
      facebook_page_id: "33333333-3333-4333-8333-333333333333",
      button_url: "https://s.click.aliexpress.com/e/_promo",
    });
    expect(payload).not.toHaveProperty("channel_id");
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

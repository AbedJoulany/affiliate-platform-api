import { describe, expect, it } from "vitest";
import { normalizeProduct } from "./normalize";

describe("normalizeProduct", () => {
  it("normalizes Decimal JSON strings for inventory formatting", () => {
    const product = normalizeProduct({
      id: "1",
      aliexpress_product_id: "sku-1",
      title: "Product",
      description: null,
      price: "12.40",
      original_price: "20",
      discount: "38",
      rating: "4.82",
      sales: "12400",
      reviews: "300",
      image_url: "",
      gallery_images: null,
      product_url: "https://example.com",
      affiliate_url: null,
      category: "Electronics",
      store_name: "Store",
      currency: "USD",
      commission_rate: "8",
      shipping_info: null,
      score: "82.347239",
      status: "active",
      last_synced_at: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    expect(product.price).toBe(12.4);
    expect(product.rating).toBe(4.82);
    expect(product.sales).toBe(12400);
    expect(product.score).toBe(82.347239);
    expect(product.rating.toFixed(2)).toBe("4.82");
  });
});

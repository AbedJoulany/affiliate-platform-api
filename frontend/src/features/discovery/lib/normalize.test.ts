import { describe, expect, it } from "vitest";
import { normalizeDiscoveryProduct, normalizeDiscoveryResponse } from "./normalize";

describe("normalizeDiscoveryProduct", () => {
  it("coerces string numerics from the API into numbers", () => {
    const product = normalizeDiscoveryProduct({
      aliexpress_product_id: "1",
      title: "Test",
      description: null,
      price: "19.99",
      original_price: "29.99",
      discount: "40",
      rating: "4.50",
      sales: "1500",
      reviews: "120",
      image_url: "https://example.com/a.jpg",
      gallery_images: [],
      product_url: "https://example.com/p",
      affiliate_url: null,
      category: null,
      store_name: null,
      currency: "USD",
      commission_rate: "8.5",
      shipping_info: null,
      score: "71.2345",
    });

    expect(product.price).toBe(19.99);
    expect(product.original_price).toBe(29.99);
    expect(product.discount).toBe(40);
    expect(product.rating).toBe(4.5);
    expect(product.sales).toBe(1500);
    expect(product.reviews).toBe(120);
    expect(product.commission_rate).toBe(8.5);
    expect(product.score).toBe(71.2345);
    expect(product.score.toFixed(2)).toBe("71.23");
  });
});

describe("normalizeDiscoveryResponse", () => {
  it("normalizes items and pagination counters", () => {
    const response = normalizeDiscoveryResponse({
      items: [
        {
          aliexpress_product_id: "1",
          title: "Test",
          description: null,
          price: "10",
          original_price: null,
          discount: "5",
          rating: "4",
          sales: "10",
          reviews: "1",
          image_url: "https://example.com/a.jpg",
          gallery_images: [],
          product_url: "https://example.com/p",
          affiliate_url: null,
          category: null,
          store_name: null,
          currency: "USD",
          commission_rate: null,
          shipping_info: null,
          score: "1",
        },
      ],
      total: "100",
      skip: "0",
      limit: "20",
      page: "2",
      total_pages: "5",
      mode: "hot",
      sort: "orders_desc",
      persisted_count: "0",
    });

    expect(response.items[0].score).toBe(1);
    expect(response.total).toBe(100);
    expect(response.page).toBe(2);
    expect(response.total_pages).toBe(5);
  });
});

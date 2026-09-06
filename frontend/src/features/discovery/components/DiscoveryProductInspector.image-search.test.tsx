import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoveryProductInspector } from "./DiscoveryProductInspector";
import type { DiscoveryProduct } from "../types/api";

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => createElement("img", { alt }),
}));

const product: DiscoveryProduct = {
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

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
});

afterEach(cleanup);

describe("DiscoveryProductInspector image selection", () => {
  it("highlights the selected gallery image and uses it for queue drafts", async () => {
    const user = userEvent.setup();
    const onAddToQueue = vi.fn();
    render(
      createElement(DiscoveryProductInspector, {
        product,
        open: true,
        canImport: true,
        importing: false,
        onClose: vi.fn(),
        onImport: vi.fn(),
        onGenerateAi: vi.fn(),
        onAddToQueue,
      }),
    );

    const thumbs = screen.getAllByLabelText("اختيار صورة المنتج");
    expect(thumbs[0]).toHaveAttribute("aria-pressed", "true");
    await user.click(thumbs[1]);
    expect(thumbs[1]).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "إضافة إلى قائمة النشر" }));
    expect(onAddToQueue).toHaveBeenCalledWith(
      expect.objectContaining({ image_url: "https://example.com/alt.jpg" }),
    );
  });

  it("searches by the selected gallery image", async () => {
    const user = userEvent.setup();
    const onSearchByImage = vi.fn();
    render(
      createElement(DiscoveryProductInspector, {
        product,
        open: true,
        canImport: true,
        importing: false,
        onClose: vi.fn(),
        onImport: vi.fn(),
        onGenerateAi: vi.fn(),
        onAddToQueue: vi.fn(),
        onSearchByImage,
      }),
    );

    await user.click(screen.getAllByLabelText("اختيار صورة المنتج")[1]);
    await user.click(screen.getByRole("button", { name: "بحث بمنتجات مشابهة" }));
    expect(onSearchByImage).toHaveBeenCalledWith("https://example.com/alt.jpg");
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoveryResultsTable } from "./DiscoveryResultsTable";
import { DEFAULT_VISIBLE_COLUMNS } from "../lib/ui-prefs";
import type { DiscoveryProduct } from "../types/api";

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => createElement("img", { alt }),
}));

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
  gallery_images: [],
  product_url: "https://www.aliexpress.com/item/100500.html",
  affiliate_url: null,
  category: null,
  store_name: null,
  currency: "USD",
  commission_rate: 8,
  shipping_info: null,
  score: 82,
};

afterEach(cleanup);

function renderTable(canImport: boolean, onImport = vi.fn()) {
  return render(
    createElement(DiscoveryResultsTable, {
      items: [product],
      selectedIds: [],
      allSelected: false,
      importedIds: new Set<string>(),
      canImport,
      importingId: null,
      visibleColumns: DEFAULT_VISIBLE_COLUMNS,
      onToggle: vi.fn(),
      onToggleAll: vi.fn(),
      onInspect: vi.fn(),
      onImport,
      onGenerateAi: vi.fn(),
      onAddToQueue: vi.fn(),
    }),
  );
}

describe("Discovery Import button", () => {
  it("stays disabled for non-admin (canImport=false) and does not call onImport", async () => {
    const onImport = vi.fn();
    renderTable(false, onImport);
    const button = screen.getByRole("button", { name: "استيراد" });
    expect(button).toBeDisabled();
    expect(onImport).not.toHaveBeenCalled();
  });

  it("is enabled for admin and calls onImport", async () => {
    const onImport = vi.fn();
    renderTable(true, onImport);
    const button = screen.getByRole("button", { name: "استيراد" });
    expect(button).toBeEnabled();
    await userEvent.click(button);
    expect(onImport).toHaveBeenCalledWith(product);
  });
});

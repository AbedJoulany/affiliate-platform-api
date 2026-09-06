import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DiscoveryView } from "./DiscoveryView";
import { searchProductsByImage } from "../api/discovery.api";
import { productKeys } from "@/features/products/hooks/useProducts";
import { clearActiveWorkspaceId, setActiveWorkspaceId } from "@/lib/workspace";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";
import type { DiscoveryProduct, DiscoveryResponse } from "../types/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/image", () => ({
  default: ({ alt }: { alt: string }) => createElement("img", { alt }),
}));

vi.mock("@/features/auth/hooks/useAuth", () => ({
  useCurrentUser: () => ({
    data: { role: "admin", default_workspace_id: null },
    isSuccess: true,
  }),
}));

vi.mock("@/features/categories/hooks/useCategories", () => ({
  useCategories: () => ({ data: { items: [] }, isSuccess: true }),
}));

vi.mock("../api/discovery.api", () => ({
  discoverProducts: vi.fn(),
  searchProductsByImage: vi.fn(),
  importProduct: vi.fn(),
  importProductsBatch: vi.fn(),
}));

vi.mock("@/features/queue/api/queue.api", () => ({
  createQueueItem: vi.fn(),
}));

vi.mock("@/features/ai/api/ai.api", () => ({
  generateContent: vi.fn(),
}));

import { createQueueItem } from "@/features/queue/api/queue.api";
import { importProduct } from "../api/discovery.api";

const searchMock = vi.mocked(searchProductsByImage);
const importMock = vi.mocked(importProduct);
const createQueueMock = vi.mocked(createQueueItem);

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

function discoveryResponse(items: DiscoveryProduct[]): DiscoveryResponse {
  return {
    items,
    total: items.length,
    skip: 0,
    limit: 20,
    page: 1,
    total_pages: 1,
    mode: "general",
    sort: "orders_desc",
    persisted_count: 0,
  };
}

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    client,
    ...render(createElement(DiscoveryView), {
      wrapper: ({ children }: { children: ReactNode }) =>
        createElement(QueryClientProvider, { client }, children),
    }),
  };
}

beforeEach(() => {
  session.clear();
  sessionStorage.clear();
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

afterEach(() => {
  cleanup();
  session.clear();
  sessionStorage.clear();
  vi.clearAllMocks();
});

describe("Discovery image search flow", () => {
  it("keeps the existing discovery empty state until image search runs", () => {
    renderView();
    expect(screen.getByText("ابدأ مساحة اكتشاف المنتجات")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "بحث بالصورة" })).toBeInTheDocument();
  });

  it("shows a loading state while searching", async () => {
    const user = userEvent.setup();
    let resolveSearch: ((value: DiscoveryResponse) => void) | undefined;
    searchMock.mockReturnValue(
      new Promise((resolve) => {
        resolveSearch = resolve;
      }),
    );

    renderView();
    await user.type(screen.getByLabelText("رابط الصورة"), "https://example.com/product.jpg");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));

    expect(await screen.findByLabelText("جار التحميل")).toBeInTheDocument();
    resolveSearch?.(discoveryResponse([product]));
    expect(await screen.findByText("Wireless Earbuds")).toBeInTheDocument();
  });

  it("renders matching products from image search without a workspace id", async () => {
    const user = userEvent.setup();
    clearActiveWorkspaceId();
    searchMock.mockResolvedValue(discoveryResponse([product]));

    renderView();
    await user.type(screen.getByLabelText("رابط الصورة"), "https://example.com/product.jpg");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));

    expect(await screen.findByText("Wireless Earbuds")).toBeInTheDocument();
    expect(searchMock).toHaveBeenCalledWith({
      image_url: "https://example.com/product.jpg",
      page: 1,
      page_size: 20,
    });
  });

  it("shows لا توجد صور مطابقة when the provider returns no items", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue(discoveryResponse([]));

    renderView();
    await user.type(screen.getByLabelText("رابط الصورة"), "https://example.com/product.jpg");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));

    expect(await screen.findByText("لا توجد صور مطابقة")).toBeInTheDocument();
  });

  it("shows the API error message when image search fails", async () => {
    const user = userEvent.setup();
    searchMock.mockRejectedValue({ status: 502, message: "مزود الصور غير متاح" });

    renderView();
    await user.type(screen.getByLabelText("رابط الصورة"), "https://example.com/product.jpg");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("مزود الصور غير متاح");
  });

  it("selects a gallery image and reflects it on the queue draft", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue(discoveryResponse([product]));
    createQueueMock.mockResolvedValue({ id: "q-1" } as never);

    renderView();
    await user.type(screen.getByLabelText("رابط الصورة"), "https://example.com/product.jpg");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));
    await screen.findByText("Wireless Earbuds");

    await user.click(screen.getByRole("button", { name: "معاينة" }));
    await user.click(screen.getAllByLabelText("اختيار صورة المنتج")[1]);
    await user.click(screen.getByRole("button", { name: "إضافة إلى قائمة النشر" }));

    await waitFor(() => expect(createQueueMock).toHaveBeenCalledTimes(1));
    expect(createQueueMock).toHaveBeenCalledWith(
      expect.objectContaining({ image_url: "https://example.com/alt.jpg" }),
    );
  });

  it("does not refetch the same image URL while results are fresh", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue(discoveryResponse([product]));

    renderView();
    await user.type(screen.getByLabelText("رابط الصورة"), "https://example.com/product.jpg");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));
    await screen.findByText("Wireless Earbuds");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));

    expect(searchMock).toHaveBeenCalledTimes(1);
  });

  it("invalidates the global product query after import, not tenant queries", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue(discoveryResponse([product]));
    importMock.mockResolvedValue({
      imported: true,
      aliexpress_product_id: "100500",
      product: { id: "p-1" },
    } as never);

    setActiveWorkspaceId(WORKSPACE_A);
    const { client } = renderView();
    client.setQueryData(productKeys.all, { items: [] });
    client.setQueryData(["queue", WORKSPACE_A], { items: [] });

    await user.type(screen.getByLabelText("رابط الصورة"), "https://example.com/product.jpg");
    await user.click(screen.getByRole("button", { name: "بحث بالصورة" }));
    await screen.findByText("Wireless Earbuds");
    await user.click(screen.getByRole("button", { name: "استيراد" }));

    await waitFor(() => expect(importMock.mock.calls[0]?.[0]).toBe("100500"));
    expect(client.getQueryState(productKeys.all)?.isInvalidated).toBe(true);
    expect(client.getQueryState(["queue", WORKSPACE_A])?.isInvalidated).not.toBe(true);
  });
});

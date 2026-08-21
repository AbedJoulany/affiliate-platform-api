import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useProducts } from "./useProducts";
import { getProducts } from "../api/products.api";
import { session } from "@/services/session";

vi.mock("../api/products.api", () => ({
  getProducts: vi.fn(),
  getProduct: vi.fn(),
  updateProduct: vi.fn(),
  deleteProduct: vi.fn(),
}));

const getProductsMock = vi.mocked(getProducts);

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return createElement(QueryClientProvider, { client }, children);
}

afterEach(() => {
  session.clear();
  vi.clearAllMocks();
});

describe("useProducts remains global", () => {
  it("fetches products without an active workspace", async () => {
    getProductsMock.mockResolvedValue({ items: [], total: 0, skip: 0, limit: 25 });
    const { result } = renderHook(() => useProducts({ skip: 0, limit: 25 }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getProductsMock).toHaveBeenCalledTimes(1);
  });
});

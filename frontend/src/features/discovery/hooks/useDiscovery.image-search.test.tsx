import { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { searchProductsByImage } from "@/features/discovery/api/discovery.api";
import {
  imageSearchKeys,
  useImageSearchQuery,
} from "@/features/discovery/hooks/useDiscovery";
import {
  WORKSPACE_HEADER,
  clearActiveWorkspaceId,
  setActiveWorkspaceId,
} from "@/lib/workspace";
import { apiClient } from "@/services/api-client";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";
import type { DiscoveryResponse } from "../types/api";

type MockResult = { status: number; data?: unknown };

const originalAdapter = apiClient.defaults.adapter;

const emptyResponse: DiscoveryResponse = {
  items: [],
  total: 0,
  skip: 0,
  limit: 20,
  page: 1,
  total_pages: 1,
  mode: "general",
  sort: "orders_desc",
  persisted_count: 0,
};

function headerValue(
  config: InternalAxiosRequestConfig,
  name: string,
): string | undefined {
  const headers = config.headers;
  if (!headers) return undefined;
  const value =
    typeof headers.get === "function" ? headers.get(name) : headers[name];
  return value == null ? undefined : String(value);
}

function installAdapter(
  handler: (config: InternalAxiosRequestConfig) => Promise<MockResult> | MockResult,
) {
  apiClient.defaults.adapter = async (config) => {
    const result = await handler(config);
    const response = {
      data: result.data ?? {},
      status: result.status,
      statusText: result.status >= 400 ? "Error" : "OK",
      headers: {},
      config,
    };
    if (result.status >= 400) {
      throw new AxiosError(
        "Request failed",
        AxiosError.ERR_BAD_RESPONSE,
        config,
        undefined,
        response,
      );
    }
    return response;
  };
}

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children);
  }
  return Wrapper;
}

beforeEach(() => {
  session.clear();
  session.setTokens("access-old", "refresh-old");
});

afterEach(() => {
  session.clear();
  apiClient.defaults.adapter = originalAdapter;
});

describe("product image search is global", () => {
  it("uses a query key without workspaceId", () => {
    const key = imageSearchKeys.search({
      source: "url",
      image_url: "https://example.com/product.jpg",
      page: 1,
    });
    expect(key).toEqual([
      "product-image-search",
      {
        source: "url",
        image_url: "https://example.com/product.jpg",
        page: 1,
      },
    ]);
    expect(JSON.stringify(key)).not.toContain(WORKSPACE_A);
    expect(key).not.toEqual(expect.arrayContaining([expect.anything(), WORKSPACE_A]));
  });

  it("POSTs /products/search/image without X-Workspace-Id even when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    let header: string | undefined;
    let url: string | undefined;
    installAdapter((config) => {
      header = headerValue(config, WORKSPACE_HEADER);
      url = config.url;
      return { status: 200, data: emptyResponse };
    });

    await searchProductsByImage({ image_url: "https://example.com/product.jpg" });
    expect(url).toBe("/products/search/image");
    expect(header).toBeUndefined();
  });

  it("searches when workspaceId is null", async () => {
    clearActiveWorkspaceId();
    let header: string | undefined;
    installAdapter((config) => {
      header = headerValue(config, WORKSPACE_HEADER);
      return { status: 200, data: emptyResponse };
    });

    const { result } = renderHook(
      () =>
        useImageSearchQuery(
          { source: "url", image_url: "https://example.com/product.jpg", page: 1 },
          true,
        ),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toEqual([]);
    expect(header).toBeUndefined();
  });

  it("surfaces provider errors instead of swallowing them", async () => {
    installAdapter(() => ({
      status: 502,
      data: { detail: "مزود الصور غير متاح" },
    }));

    const { result } = renderHook(
      () =>
        useImageSearchQuery(
          { source: "url", image_url: "https://example.com/product.jpg", page: 1 },
          true,
        ),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toMatchObject({
      status: 502,
      message: "مزود الصور غير متاح",
    });
  });
});

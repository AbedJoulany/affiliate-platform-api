import { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { importProduct } from "@/features/discovery/api/discovery.api";
import { useImportProduct } from "@/features/discovery/hooks/useDiscovery";
import { productKeys } from "@/features/products/hooks/useProducts";
import {
  WORKSPACE_HEADER,
  clearActiveWorkspaceId,
  setActiveWorkspaceId,
} from "@/lib/workspace";
import { apiClient } from "@/services/api-client";
import { session } from "@/services/session";
import { WORKSPACE_A } from "@/test/workspace";

type MockResult = { status: number; data?: unknown };

const originalAdapter = apiClient.defaults.adapter;

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

beforeEach(() => {
  session.clear();
  session.setTokens("access-old", "refresh-old");
});

afterEach(() => {
  session.clear();
  apiClient.defaults.adapter = originalAdapter;
});

describe("product import stays global", () => {
  it("POSTs /products/import without X-Workspace-Id even when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    let header: string | undefined;
    let url: string | undefined;
    installAdapter((config) => {
      header = headerValue(config, WORKSPACE_HEADER);
      url = config.url;
      return {
        status: 201,
        data: {
          imported: true,
          aliexpress_product_id: "100500",
          product: { id: "p-1" },
        },
      };
    });

    await importProduct("100500");
    expect(url).toBe("/products/import");
    expect(header).toBeUndefined();
  });

  it("POSTs /products/import without a workspace id present", async () => {
    clearActiveWorkspaceId();
    let header: string | undefined;
    installAdapter((config) => {
      header = headerValue(config, WORKSPACE_HEADER);
      return {
        status: 201,
        data: { imported: true, aliexpress_product_id: "100500", product: { id: "p-1" } },
      };
    });

    await importProduct("100500");
    expect(header).toBeUndefined();
  });

  it("invalidates product queries after a successful import", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    client.setQueryData(productKeys.all, { items: [] });
    installAdapter(() => ({
      status: 201,
      data: { imported: true, aliexpress_product_id: "100500", product: { id: "p-1" } },
    }));

    const { result } = renderHook(() => useImportProduct(), {
      wrapper: ({ children }: { children: ReactNode }) =>
        createElement(QueryClientProvider, { client }, children),
    });

    result.current.mutate("100500");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getQueryState(productKeys.all)?.isInvalidated).toBe(true);
  });
});

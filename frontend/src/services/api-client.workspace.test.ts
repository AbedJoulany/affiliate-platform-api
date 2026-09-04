import { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { joinCampaign } from "@/features/affiliates/api/affiliates.api";
import { getProducts } from "@/features/products/api/products.api";
import {
  WORKSPACE_HEADER,
  clearActiveWorkspaceId,
  setActiveWorkspaceId,
} from "@/lib/workspace";
import { apiClient, MISSING_WORKSPACE_ERROR } from "./api-client";
import { session } from "./session";
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

describe("apiClient workspace header", () => {
  it("sends X-Workspace-Id on workspace-scoped requests when a workspace is active", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    const seen: Record<string, string | undefined> = {};
    installAdapter((config) => {
      seen[String(config.url)] = headerValue(config, WORKSPACE_HEADER);
      return { status: 200, data: { items: [] } };
    });

    await apiClient.get("/queues");
    await apiClient.get("/channels");
    await apiClient.get("/dashboard");
    await apiClient.get("/analytics/overview");
    await apiClient.get("/workspace-settings");
    await apiClient.get("/campaigns");
    await apiClient.post("/conversions", { amount: 1 });
    await apiClient.post("/affiliates/join-campaign", { campaign_id: "camp-1" });

    expect(seen).toEqual({
      "/queues": WORKSPACE_A,
      "/channels": WORKSPACE_A,
      "/dashboard": WORKSPACE_A,
      "/analytics/overview": WORKSPACE_A,
      "/workspace-settings": WORKSPACE_A,
      "/campaigns": WORKSPACE_A,
      "/conversions": WORKSPACE_A,
      "/affiliates/join-campaign": WORKSPACE_A,
    });
  });

  it("blocks workspace-scoped requests when no workspace is active and does not send a header", async () => {
    let called = false;
    installAdapter(() => {
      called = true;
      return { status: 200, data: { items: [] } };
    });

    await expect(apiClient.get("/queues")).rejects.toMatchObject(
      MISSING_WORKSPACE_ERROR,
    );
    expect(called).toBe(false);
  });

  it("does not send undefined, null, empty, or non-UUID workspace headers", async () => {
    const seen: Array<string | undefined> = [];
    installAdapter((config) => {
      seen.push(headerValue(config, WORKSPACE_HEADER));
      return { status: 200, data: { items: [] } };
    });

    await expect(apiClient.get("/channels")).rejects.toMatchObject(
      MISSING_WORKSPACE_ERROR,
    );

    setActiveWorkspaceId("undefined");
    await expect(apiClient.get("/dashboard")).rejects.toMatchObject(
      MISSING_WORKSPACE_ERROR,
    );

    setActiveWorkspaceId("null");
    await expect(apiClient.post("/conversions", { amount: 1 })).rejects.toMatchObject(
      MISSING_WORKSPACE_ERROR,
    );

    session.setActiveWorkspaceId("invalid-value");
    await expect(apiClient.get("/queues")).rejects.toMatchObject(
      MISSING_WORKSPACE_ERROR,
    );

    expect(seen).toEqual([]);
  });

  it("lets GET /products succeed without workspace context and without the header", async () => {
    clearActiveWorkspaceId();
    const seen: Array<{ url?: string; header?: string }> = [];
    installAdapter((config) => {
      seen.push({
        url: config.url,
        header: headerValue(config, WORKSPACE_HEADER),
      });
      if (String(config.url).includes("/products/discover")) {
        return { status: 200, data: { items: [], total: 0 } };
      }
      if (String(config.url).startsWith("/products/")) {
        return {
          status: 200,
          data: {
            id: "p-1",
            title: "Product",
            price: 1,
            original_price: null,
            discount: 0,
            rating: 0,
            sales: 0,
            reviews: 0,
            commission_rate: null,
            score: 0,
            status: "active",
            category: null,
            store_name: null,
            aliexpress_product_id: "1",
            image_url: null,
            created_at: "2026-08-13T00:00:00Z",
            updated_at: "2026-08-13T00:00:00Z",
          },
        };
      }
      return { status: 200, data: { items: [], total: 0, skip: 0, limit: 20 } };
    });

    const result = await getProducts();
    await apiClient.get("/products/p-1");
    await apiClient.get("/products/discover");
    expect(seen.map((entry) => entry.url)).toEqual([
      "/products",
      "/products/p-1",
      "/products/discover",
    ]);
    expect(seen.every((entry) => entry.header === undefined)).toBe(true);
    expect(result.total).toBe(0);
  });

  it("does not attach X-Workspace-Id to global product, auth, or affiliate-profile requests", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    const seen: Record<string, string | undefined> = {};
    installAdapter((config) => {
      seen[String(config.url)] = headerValue(config, WORKSPACE_HEADER);
      return { status: 200, data: { items: [], total: 0, skip: 0, limit: 20 } };
    });

    await apiClient.get("/products");
    await apiClient.get("/auth/me");
    await apiClient.patch("/auth/me", { full_name: "Ada" });
    await apiClient.get("/affiliates/me");
    await apiClient.post("/products/search/image", {
      image_url: "https://example.com/product.jpg",
    });
    expect(seen).toEqual({
      "/products": undefined,
      "/auth/me": undefined,
      "/affiliates/me": undefined,
      "/products/search/image": undefined,
    });
  });

  it("sends X-Workspace-Id on POST /affiliates/join-campaign without putting workspace in the body", async () => {
    setActiveWorkspaceId(WORKSPACE_A);
    let header: string | undefined;
    let body: unknown;
    let url: string | undefined;
    installAdapter((config) => {
      header = headerValue(config, WORKSPACE_HEADER);
      url = config.url;
      body = typeof config.data === "string" ? JSON.parse(config.data) : config.data;
      return {
        status: 201,
        data: {
          id: "join-1",
          affiliate_id: "aff-1",
          campaign_id: "camp-1",
          tracking_link: "https://example.test/t",
          created_at: "2026-08-13T00:00:00Z",
          updated_at: "2026-08-13T00:00:00Z",
        },
      };
    });

    await joinCampaign({ campaign_id: "camp-1" });
    expect(url).toBe("/affiliates/join-campaign");
    expect(header).toBe(WORKSPACE_A);
    expect(body).toEqual({ campaign_id: "camp-1" });
  });
});

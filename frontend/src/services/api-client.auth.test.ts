import { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./api-client";
import { session } from "./session";
import { setActiveWorkspaceId } from "@/lib/workspace";
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
  setActiveWorkspaceId(WORKSPACE_A);
});

afterEach(() => {
  session.clear();
  apiClient.defaults.adapter = originalAdapter;
  vi.unstubAllGlobals();
});

describe("apiClient authentication", () => {
  it("attaches the access token as a Bearer header", async () => {
    let authorization: string | undefined;
    installAdapter((config) => {
      authorization = headerValue(config, "Authorization");
      return { status: 200, data: { ok: true } };
    });

    await apiClient.get("/dashboard");
    expect(authorization).toBe("Bearer access-old");
  });

  it("sends POST /conversions with the access token", async () => {
    let authorization: string | undefined;
    let method: string | undefined;
    let url: string | undefined;
    installAdapter((config) => {
      authorization = headerValue(config, "Authorization");
      method = config.method;
      url = config.url;
      return { status: 201, data: { id: "conv-1" } };
    });

    await apiClient.post("/conversions", { affiliate_id: "aff-1", amount: 10 });
    expect(method).toBe("post");
    expect(url).toBe("/conversions");
    expect(authorization).toBe("Bearer access-old");
  });

  it("refreshes once on 401, stores rotated tokens, and retries the original request", async () => {
    const calls: Array<{ url?: string; authorization?: string; body?: unknown }> = [];
    installAdapter((config) => {
      calls.push({
        url: config.url,
        authorization: headerValue(config, "Authorization"),
        body: config.data,
      });
      if (config.url === "/auth/refresh") {
        expect(headerValue(config, "Authorization")).not.toContain("refresh-old");
        return {
          status: 200,
          data: {
            access_token: "access-new",
            token_type: "bearer",
            refresh_token: "refresh-new",
          },
        };
      }
      if (headerValue(config, "Authorization") === "Bearer access-new") {
        return { status: 200, data: { items: [] } };
      }
      return { status: 401, data: { detail: "expired" } };
    });

    const { data } = await apiClient.get("/queues");
    expect(data).toEqual({ items: [] });
    expect(session.getAccessToken()).toBe("access-new");
    expect(session.getRefreshToken()).toBe("refresh-new");
    expect(calls.filter((call) => call.url === "/auth/refresh")).toHaveLength(1);
    expect(calls.filter((call) => call.url === "/queues")).toHaveLength(2);
  });

  it("shares one refresh request across concurrent 401s", async () => {
    let releaseRefresh: () => void = () => undefined;
    const refreshGate = new Promise<void>((resolve) => {
      releaseRefresh = resolve;
    });
    let refreshCalls = 0;
    const retriedAuth = new Set<string>();

    installAdapter(async (config) => {
      if (config.url === "/auth/refresh") {
        refreshCalls += 1;
        await refreshGate;
        return {
          status: 200,
          data: {
            access_token: "access-new",
            token_type: "bearer",
            refresh_token: "refresh-new",
          },
        };
      }
      if (headerValue(config, "Authorization") === "Bearer access-new") {
        retriedAuth.add(String(config.url));
        return { status: 200, data: { ok: true } };
      }
      return { status: 401, data: { detail: "expired" } };
    });

    const pending = Promise.all([
      apiClient.get("/queues"),
      apiClient.get("/products"),
      apiClient.post("/conversions", { affiliate_id: "aff-1", amount: 25 }),
    ]);

    await vi.waitFor(() => expect(refreshCalls).toBe(1));
    releaseRefresh();
    await pending;

    expect(refreshCalls).toBe(1);
    expect(retriedAuth).toEqual(new Set(["/queues", "/products", "/conversions"]));
    expect(session.getAccessToken()).toBe("access-new");
    expect(session.getRefreshToken()).toBe("refresh-new");
  });

  it("does not refresh recursively when POST /auth/refresh returns 401", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    let refreshCalls = 0;
    installAdapter((config) => {
      if (config.url === "/auth/refresh") {
        refreshCalls += 1;
        return { status: 401, data: { detail: "invalid" } };
      }
      return { status: 401, data: { detail: "expired" } };
    });

    await expect(apiClient.get("/queues")).rejects.toMatchObject({ status: 401 });
    expect(refreshCalls).toBe(1);
    expect(session.getAccessToken()).toBeNull();
    expect(session.getRefreshToken()).toBeNull();
    expect(assign).toHaveBeenCalledWith("/login");
  });

  it("retries the original request only once after a successful refresh", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    let refreshCalls = 0;
    let queueCalls = 0;
    installAdapter((config) => {
      if (config.url === "/auth/refresh") {
        refreshCalls += 1;
        return {
          status: 200,
          data: {
            access_token: "access-new",
            token_type: "bearer",
            refresh_token: "refresh-new",
          },
        };
      }
      queueCalls += 1;
      return { status: 401, data: { detail: "expired" } };
    });

    await expect(apiClient.get("/queues")).rejects.toMatchObject({ status: 401 });
    expect(refreshCalls).toBe(1);
    expect(queueCalls).toBe(2);
    expect(session.getAccessToken()).toBeNull();
    expect(session.getRefreshToken()).toBeNull();
  });

  it("clears authentication and does not retry infinitely when refresh fails", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    let queueCalls = 0;
    installAdapter((config) => {
      if (config.url === "/auth/refresh") {
        return { status: 401, data: { detail: "reuse detected" } };
      }
      queueCalls += 1;
      return { status: 401, data: { detail: "expired" } };
    });

    await expect(apiClient.get("/queues")).rejects.toMatchObject({ status: 401 });
    expect(queueCalls).toBe(1);
    expect(session.getAccessToken()).toBeNull();
    expect(session.getRefreshToken()).toBeNull();
  });

  it("does not trigger refresh for login, refresh, or logout endpoints", async () => {
    let refreshCalls = 0;
    installAdapter((config) => {
      if (config.url === "/auth/refresh") {
        refreshCalls += 1;
        return { status: 401, data: { detail: "invalid" } };
      }
      return { status: 401, data: { detail: "unauthorized" } };
    });

    await expect(
      apiClient.post("/auth/login", new URLSearchParams(), { skipAuthRefresh: true }),
    ).rejects.toMatchObject({ status: 401 });
    await expect(
      apiClient.post("/auth/refresh", { refresh_token: "refresh-old" }, { skipAuthRefresh: true }),
    ).rejects.toMatchObject({ status: 401 });
    await expect(
      apiClient.post("/auth/logout", { refresh_token: "refresh-old" }, { skipAuthRefresh: true }),
    ).rejects.toMatchObject({ status: 401 });

    expect(refreshCalls).toBe(1);
    expect(session.getAccessToken()).toBe("access-old");
    expect(session.getRefreshToken()).toBe("refresh-old");
  });

  it("does not refresh or log out on 403", async () => {
    let refreshCalls = 0;
    installAdapter((config) => {
      if (config.url === "/auth/refresh") {
        refreshCalls += 1;
        return { status: 200, data: {} };
      }
      return { status: 403, data: { detail: "forbidden" } };
    });

    await expect(
      apiClient.post("/conversions", { affiliate_id: "other", amount: 10 }),
    ).rejects.toMatchObject({ status: 403 });
    expect(refreshCalls).toBe(0);
    expect(session.getAccessToken()).toBe("access-old");
    expect(session.getRefreshToken()).toBe("refresh-old");
  });

  it("sends the refresh token only in the JSON body, never as Bearer", async () => {
    let refreshAuthorization: string | undefined;
    let refreshBody: unknown;
    installAdapter((config) => {
      if (config.url === "/auth/refresh") {
        refreshAuthorization = headerValue(config, "Authorization");
        refreshBody =
          typeof config.data === "string" ? JSON.parse(config.data) : config.data;
        return {
          status: 200,
          data: {
            access_token: "access-new",
            token_type: "bearer",
            refresh_token: "refresh-new",
          },
        };
      }
      if (headerValue(config, "Authorization") === "Bearer access-new") {
        return { status: 200, data: { ok: true } };
      }
      return { status: 401, data: { detail: "expired" } };
    });

    await apiClient.get("/channels");
    expect(refreshAuthorization).toBe("Bearer access-old");
    expect(refreshBody).toEqual({ refresh_token: "refresh-old" });
    expect(refreshAuthorization).not.toContain("refresh-old");
  });
});

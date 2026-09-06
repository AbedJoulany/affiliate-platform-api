import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  applyDefaultWorkspaceFromUser,
  clearActiveWorkspaceId,
  getActiveWorkspaceId,
  isUsableWorkspaceId,
  isWorkspaceScopedPath,
  isWorkspaceScopedQueryKey,
  removeWorkspaceScopedQueries,
  setActiveWorkspaceId,
  workspaceScopedQueryKey,
} from "./workspace";
import { session } from "@/services/session";
import { WORKSPACE_A, WORKSPACE_B } from "@/test/workspace";

afterEach(() => {
  session.clear();
  vi.unstubAllEnvs();
});

describe("isUsableWorkspaceId", () => {
  it("accepts a UUID and rejects empty, undefined, null, and non-UUID values", () => {
    expect(isUsableWorkspaceId(WORKSPACE_A)).toBe(true);
    expect(isUsableWorkspaceId(` ${WORKSPACE_A} `)).toBe(true);
    expect(isUsableWorkspaceId("undefined")).toBe(false);
    expect(isUsableWorkspaceId("null")).toBe(false);
    expect(isUsableWorkspaceId("")).toBe(false);
    expect(isUsableWorkspaceId("invalid-value")).toBe(false);
    expect(isUsableWorkspaceId("not-a-uuid")).toBe(false);
    expect(isUsableWorkspaceId(undefined)).toBe(false);
    expect(isUsableWorkspaceId(null)).toBe(false);
  });
});

describe("active workspace persistence", () => {
  it("stores a usable id, reads it back, and clears it", () => {
    setActiveWorkspaceId(WORKSPACE_A);
    expect(getActiveWorkspaceId()).toBe(WORKSPACE_A);
    expect(session.getActiveWorkspaceId()).toBe(WORKSPACE_A);
    clearActiveWorkspaceId();
    expect(getActiveWorkspaceId()).toBeNull();
    expect(session.getActiveWorkspaceId()).toBeNull();
  });

  it("ignores invalid stored values rather than returning them", () => {
    session.setActiveWorkspaceId("invalid-value");
    expect(session.getActiveWorkspaceId()).toBe("invalid-value");
    expect(getActiveWorkspaceId()).toBeNull();
    setActiveWorkspaceId("undefined");
    expect(getActiveWorkspaceId()).toBeNull();
    setActiveWorkspaceId("null");
    expect(getActiveWorkspaceId()).toBeNull();
  });

  it("uses NEXT_PUBLIC_WORKSPACE_ID only when storage has no valid workspace", () => {
    vi.stubEnv("NEXT_PUBLIC_WORKSPACE_ID", WORKSPACE_B);
    expect(getActiveWorkspaceId()).toBe(WORKSPACE_B);

    setActiveWorkspaceId(WORKSPACE_A);
    expect(getActiveWorkspaceId()).toBe(WORKSPACE_A);

    session.setActiveWorkspaceId("invalid-value");
    expect(getActiveWorkspaceId()).toBe(WORKSPACE_B);
    vi.unstubAllEnvs();
  });

  it("ignores an invalid environment seed", () => {
    vi.stubEnv("NEXT_PUBLIC_WORKSPACE_ID", "invalid-value");
    expect(getActiveWorkspaceId()).toBeNull();
    vi.unstubAllEnvs();
  });
});

describe("applyDefaultWorkspaceFromUser", () => {
  it("writes a valid default_workspace_id to session storage", () => {
    applyDefaultWorkspaceFromUser({ default_workspace_id: WORKSPACE_A });
    expect(getActiveWorkspaceId()).toBe(WORKSPACE_A);
    expect(session.getActiveWorkspaceId()).toBe(WORKSPACE_A);
  });

  it("does not invent a workspace when default_workspace_id is null", () => {
    applyDefaultWorkspaceFromUser({ default_workspace_id: null });
    expect(getActiveWorkspaceId()).toBeNull();
  });

  it("ignores invalid default_workspace_id values", () => {
    applyDefaultWorkspaceFromUser({ default_workspace_id: "undefined" });
    applyDefaultWorkspaceFromUser({ default_workspace_id: "admin@localhost" });
    expect(getActiveWorkspaceId()).toBeNull();
  });
});

describe("isWorkspaceScopedPath", () => {
  it("classifies tenant APIs as workspace-scoped", () => {
    expect(isWorkspaceScopedPath("/queues")).toBe(true);
    expect(isWorkspaceScopedPath("/queues/abc/attempts")).toBe(true);
    expect(isWorkspaceScopedPath("/channels")).toBe(true);
    expect(isWorkspaceScopedPath("/dashboard")).toBe(true);
    expect(isWorkspaceScopedPath("/workspace-settings")).toBe(true);
    expect(isWorkspaceScopedPath("http://localhost:8000/api/v1/queues/stream")).toBe(
      true,
    );
  });

  it("keeps global catalog and auth APIs unscoped", () => {
    expect(isWorkspaceScopedPath("/products")).toBe(false);
    expect(isWorkspaceScopedPath("/products/abc")).toBe(false);
    expect(isWorkspaceScopedPath("/products/discover")).toBe(false);
    expect(isWorkspaceScopedPath("/products/search/image")).toBe(false);
    expect(isWorkspaceScopedPath("/products/import")).toBe(false);
    expect(isWorkspaceScopedPath("/auth/me")).toBe(false);
    expect(isWorkspaceScopedPath("/auth/login")).toBe(false);
    expect(isWorkspaceScopedPath("/aliexpress/categories")).toBe(false);
    expect(isWorkspaceScopedPath("/ai-content/generate")).toBe(false);
  });
});

describe("workspace query keys", () => {
  it("gives queues, channels, and dashboard distinct identities per workspace", () => {
    expect(workspaceScopedQueryKey("queue", WORKSPACE_A)).not.toEqual(
      workspaceScopedQueryKey("queue", WORKSPACE_B),
    );
    expect(workspaceScopedQueryKey("channels", WORKSPACE_A)).not.toEqual(
      workspaceScopedQueryKey("channels", WORKSPACE_B),
    );
    expect(workspaceScopedQueryKey("dashboard", WORKSPACE_A)).not.toEqual(
      workspaceScopedQueryKey("dashboard", WORKSPACE_B),
    );
    expect(workspaceScopedQueryKey("workspace-settings", WORKSPACE_A)).not.toEqual(
      workspaceScopedQueryKey("workspace-settings", WORKSPACE_B),
    );
    expect(isWorkspaceScopedQueryKey(["products"])).toBe(false);
    expect(isWorkspaceScopedQueryKey(["product-image-search", { page: 1 }])).toBe(false);
    expect(isWorkspaceScopedQueryKey(["queue", WORKSPACE_A])).toBe(true);
  });

  it("removes tenant cache without touching global product queries", () => {
    const client = new QueryClient();
    client.setQueryData(["queue", WORKSPACE_A], { items: ["a"] });
    client.setQueryData(["channels", WORKSPACE_A], { items: ["ch"] });
    client.setQueryData(["dashboard", WORKSPACE_A], { products: { total: 1 } });
    client.setQueryData(["workspace-settings", WORKSPACE_A], { timezone: "UTC" });
    client.setQueryData(["products"], { items: ["p"] });

    removeWorkspaceScopedQueries(client);

    expect(client.getQueryData(["queue", WORKSPACE_A])).toBeUndefined();
    expect(client.getQueryData(["channels", WORKSPACE_A])).toBeUndefined();
    expect(client.getQueryData(["dashboard", WORKSPACE_A])).toBeUndefined();
    expect(client.getQueryData(["workspace-settings", WORKSPACE_A])).toBeUndefined();
    expect(client.getQueryData(["products"])).toEqual({ items: ["p"] });
  });
});

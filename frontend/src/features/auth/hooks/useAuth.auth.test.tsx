import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { session } from "@/services/session";
import { setActiveWorkspaceId, getActiveWorkspaceId } from "@/lib/workspace";
import { WORKSPACE_A } from "@/test/workspace";
import type { TokenResponse } from "../types/api";

const replace = vi.fn();
const loginMock = vi.fn();
const logoutMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("../api/auth.api", () => ({
  login: (...args: unknown[]) => loginMock(...args),
  logout: (...args: unknown[]) => logoutMock(...args),
  getCurrentUser: vi.fn(),
  refreshSession: vi.fn(),
}));

import { useLogin, useLogout, useCurrentUser } from "./useAuth";
import { getCurrentUser } from "../api/auth.api";

const getCurrentUserMock = vi.mocked(getCurrentUser);

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return createElement(QueryClientProvider, { client }, children);
}

beforeEach(() => {
  session.clear();
  replace.mockReset();
  loginMock.mockReset();
  logoutMock.mockReset();
  getCurrentUserMock.mockReset();
});

afterEach(() => {
  session.clear();
});

describe("useLogin / useLogout", () => {
  it("stores access and refresh tokens after successful login", async () => {
    const tokens: TokenResponse = {
      access_token: "access-login",
      token_type: "bearer",
      refresh_token: "refresh-login",
    };
    loginMock.mockResolvedValue(tokens);

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ email: "owner@example.com", password: "password123" });

    await waitFor(() => expect(session.getAccessToken()).toBe("access-login"));
    expect(session.getRefreshToken()).toBe("refresh-login");
    expect(replace).toHaveBeenCalledWith("/dashboard");
    expect(loginMock).toHaveBeenCalledTimes(1);
  });

  it("calls POST logout with the refresh token and clears local state", async () => {
    session.setTokens("access-login", "refresh-login");
    setActiveWorkspaceId(WORKSPACE_A);
    logoutMock.mockResolvedValue(undefined);

    const { result } = renderHook(() => useLogout(), { wrapper });
    result.current();

    await waitFor(() => expect(logoutMock).toHaveBeenCalledWith("refresh-login"));
    await waitFor(() => expect(session.getAccessToken()).toBeNull());
    expect(session.getRefreshToken()).toBeNull();
    expect(getActiveWorkspaceId()).toBeNull();
    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("clears local auth state even if logout fails", async () => {
    session.setTokens("access-login", "refresh-login");
    logoutMock.mockRejectedValue({ status: 500, message: "تعذر إكمال الطلب." });

    const { result } = renderHook(() => useLogout(), { wrapper });
    result.current();

    await waitFor(() => expect(session.getAccessToken()).toBeNull());
    expect(session.getRefreshToken()).toBeNull();
    expect(replace).toHaveBeenCalledWith("/login");
  });
});

const sampleUser = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "owner@example.com",
  full_name: "مالك المنصة",
  role: "admin" as const,
  is_active: true,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
};

describe("useCurrentUser workspace restoration", () => {
  it("writes affiliate_active_workspace_id from default_workspace_id", async () => {
    session.setTokens("access-login", "refresh-login");
    getCurrentUserMock.mockResolvedValue({
      ...sampleUser,
      default_workspace_id: WORKSPACE_A,
    });

    const { result } = renderHook(() => useCurrentUser(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getActiveWorkspaceId()).toBe(WORKSPACE_A);
    expect(session.getActiveWorkspaceId()).toBe(WORKSPACE_A);
  });

  it("does not invent a workspace when default_workspace_id is null", async () => {
    session.setTokens("access-login", "refresh-login");
    getCurrentUserMock.mockResolvedValue({
      ...sampleUser,
      default_workspace_id: null,
    });

    const { result } = renderHook(() => useCurrentUser(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getActiveWorkspaceId()).toBeNull();
  });
});

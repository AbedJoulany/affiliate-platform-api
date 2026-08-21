import { apiClient } from "@/services/api-client";
import { applyDefaultWorkspaceFromUser } from "@/lib/workspace";
import type { LoginInput, TokenResponse, User } from "../types/api";

export async function login(input: LoginInput): Promise<TokenResponse> {
  const body = new URLSearchParams({ username: input.email, password: input.password });
  const { data } = await apiClient.post<TokenResponse>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    skipAuthRefresh: true,
  });
  return data;
}

export async function refreshSession(refreshToken: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>(
    "/auth/refresh",
    { refresh_token: refreshToken },
    { skipAuthRefresh: true },
  );
  return data;
}

export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post(
    "/auth/logout",
    { refresh_token: refreshToken },
    { skipAuthRefresh: true },
  );
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me");
  applyDefaultWorkspaceFromUser(data);
  return data;
}

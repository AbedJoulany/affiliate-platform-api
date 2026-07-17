import { apiClient } from "@/services/api-client";
import type { LoginInput, TokenResponse, User } from "../types/api";

export async function login(input: LoginInput): Promise<TokenResponse> {
  const body = new URLSearchParams({ username: input.email, password: input.password });
  const { data } = await apiClient.post<TokenResponse>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me");
  return data;
}

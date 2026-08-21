"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { getCurrentUser, login, logout } from "../api/auth.api";
import type { LoginInput, TokenResponse } from "../types/api";
import { session } from "@/services/session";
import type { ApiError } from "@/services/api-client";
import { applyDefaultWorkspaceFromUser } from "@/lib/workspace";

export const authKeys = { me: ["auth", "me"] as const };

export function useCurrentUser(enabled = true) {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: async () => {
      const user = await getCurrentUser();
      applyDefaultWorkspaceFromUser(user);
      return user;
    },
    enabled,
    retry: false,
  });
}

export function useLogin() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  return useMutation<TokenResponse, ApiError, LoginInput>({
    mutationFn: (input: LoginInput) => login(input),
    onSuccess: ({ access_token, refresh_token }) => {
      session.setTokens(access_token, refresh_token);
      void queryClient.invalidateQueries({ queryKey: authKeys.me });
      const next = searchParams.get("next");
      router.replace(next?.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
    },
  });
}

export function useLogout() {
  const router = useRouter();
  const queryClient = useQueryClient();
  return () => {
    const refreshToken = session.getRefreshToken();
    const finish = () => {
      session.clear();
      queryClient.clear();
      router.replace("/login");
    };
    if (!refreshToken) {
      finish();
      return;
    }
    void logout(refreshToken).catch(() => undefined).finally(finish);
  };
}

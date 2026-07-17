"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { getCurrentUser, login } from "../api/auth.api";
import type { LoginInput, TokenResponse } from "../types/api";
import { session } from "@/services/session";
import type { ApiError } from "@/services/api-client";

export const authKeys = { me: ["auth", "me"] as const };

export function useCurrentUser(enabled = true) {
  return useQuery({ queryKey: authKeys.me, queryFn: getCurrentUser, enabled, retry: false });
}

export function useLogin() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  return useMutation<TokenResponse, ApiError, LoginInput>({
    mutationFn: (input: LoginInput) => login(input),
    onSuccess: ({ access_token }) => {
      session.setAccessToken(access_token);
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
    session.clear();
    queryClient.clear();
    router.replace("/login");
  };
}

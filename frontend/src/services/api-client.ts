import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { session } from "@/services/session";

declare module "axios" {
  interface AxiosRequestConfig {
    /** Auth session endpoints must never trigger token refresh. */
    skipAuthRefresh?: boolean;
    /** Marks a request that has already been retried after one refresh. */
    _authRetried?: boolean;
  }
}

export interface ApiError {
  status: number;
  message: string;
  validation?: ReadonlyArray<{ loc: ReadonlyArray<string | number>; msg: string }>;
}

interface ErrorBody {
  detail?: string | ReadonlyArray<{ loc: ReadonlyArray<string | number>; msg: string }>;
}

type TokenResponse = {
  access_token: string;
  token_type: string;
  refresh_token: string;
};

type AuthRequestConfig = InternalAxiosRequestConfig & {
  skipAuthRefresh?: boolean;
  _authRetried?: boolean;
};

const AUTH_SESSION_PATH = /\/auth\/(login|refresh|logout)\/?$/;

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  timeout: 30_000,
  headers: { Accept: "application/json" },
});

let inFlightRefresh: Promise<void> | null = null;

function requestPath(url: string | undefined): string {
  if (!url) return "";
  try {
    const parsed = url.startsWith("http://") || url.startsWith("https://")
      ? new URL(url)
      : new URL(url, "http://local.invalid");
    return parsed.pathname;
  } catch {
    return url;
  }
}

function isAuthSessionRequest(config: AuthRequestConfig | undefined): boolean {
  if (!config) return false;
  if (config.skipAuthRefresh) return true;
  return AUTH_SESSION_PATH.test(requestPath(config.url));
}

function normalizeAxiosError(error: AxiosError<ErrorBody>): ApiError {
  const status = error.response?.status ?? 0;
  const detail = error.response?.data?.detail;
  return {
    status,
    message:
      typeof detail === "string"
        ? detail
        : status === 0
          ? "تعذر الاتصال بالخادم."
          : "تعذر إكمال الطلب.",
    validation: Array.isArray(detail) ? detail : undefined,
  };
}

function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  try {
    window.location.assign("/login");
  } catch {
    // jsdom and some test environments do not implement navigation.
  }
}

function clearSessionAndRedirect(): void {
  session.clear();
  redirectToLogin();
}

async function performRefresh(): Promise<void> {
  const refreshToken = session.getRefreshToken();
  if (!refreshToken) {
    throw new Error("missing_refresh_token");
  }
  const { data } = await apiClient.post<TokenResponse>(
    "/auth/refresh",
    { refresh_token: refreshToken },
    { skipAuthRefresh: true },
  );
  session.setTokens(data.access_token, data.refresh_token);
}

function refreshAccessToken(): Promise<void> {
  if (!inFlightRefresh) {
    inFlightRefresh = performRefresh().finally(() => {
      inFlightRefresh = null;
    });
  }
  return inFlightRefresh;
}

apiClient.interceptors.request.use((config) => {
  const token = session.getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ErrorBody>) => {
    const normalized = normalizeAxiosError(error);
    const status = normalized.status;
    const original = error.config as AuthRequestConfig | undefined;

    if (status !== 401) {
      return Promise.reject(normalized);
    }

    if (original?._authRetried) {
      clearSessionAndRedirect();
      return Promise.reject(normalized);
    }

    if (isAuthSessionRequest(original)) {
      return Promise.reject(normalized);
    }

    if (!session.getRefreshToken()) {
      clearSessionAndRedirect();
      return Promise.reject(normalized);
    }

    try {
      await refreshAccessToken();
      if (!original) {
        clearSessionAndRedirect();
        return Promise.reject(normalized);
      }
      original._authRetried = true;
      return apiClient.request(original);
    } catch {
      clearSessionAndRedirect();
      return Promise.reject(normalized);
    }
  },
);

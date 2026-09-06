import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import {
  WORKSPACE_HEADER,
  getActiveWorkspaceId,
  isWorkspaceScopedPath,
  requestPathname,
} from "@/lib/workspace";
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
  code?: string;
  validation?: ReadonlyArray<{ loc: ReadonlyArray<string | number>; msg: string }>;
}

export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === "object" &&
    error !== null &&
    "message" in error &&
    typeof (error as ApiError).message === "string"
  );
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (isApiError(error) && error.message.length > 0) {
    return error.message;
  }
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return fallback;
}

export const MISSING_WORKSPACE_ERROR: ApiError = {
  status: 0,
  code: "missing_workspace",
  message: "لم يتم تحديد مساحة العمل.",
};

export function isMissingWorkspaceError(error: unknown): error is ApiError {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as ApiError).code === "missing_workspace"
  );
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
  return requestPathname(url);
}

function setHeader(
  config: InternalAxiosRequestConfig,
  name: string,
  value: string,
): void {
  const headers = config.headers;
  if (headers && typeof headers.set === "function") {
    headers.set(name, value);
    return;
  }
  if (headers) {
    (headers as Record<string, string>)[name] = value;
  }
}

function deleteHeader(config: InternalAxiosRequestConfig, name: string): void {
  const headers = config.headers;
  if (!headers) return;
  if (typeof headers.delete === "function") {
    headers.delete(name);
    return;
  }
  delete (headers as Record<string, unknown>)[name];
}

function applyWorkspaceHeader(config: InternalAxiosRequestConfig): void {
  if (!isWorkspaceScopedPath(config.url)) {
    deleteHeader(config, WORKSPACE_HEADER);
    return;
  }
  const workspaceId = getActiveWorkspaceId();
  if (!workspaceId) {
    deleteHeader(config, WORKSPACE_HEADER);
    throw MISSING_WORKSPACE_ERROR;
  }
  setHeader(config, WORKSPACE_HEADER, workspaceId);
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
  try {
    applyWorkspaceHeader(config);
  } catch (error) {
    return Promise.reject(error);
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) {
      return Promise.reject(error);
    }

    const normalized = normalizeAxiosError(error as AxiosError<ErrorBody>);
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

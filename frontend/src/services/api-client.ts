import axios, { AxiosError } from "axios";
import { session } from "@/services/session";

export interface ApiError {
  status: number;
  message: string;
  validation?: ReadonlyArray<{ loc: ReadonlyArray<string | number>; msg: string }>;
}

interface ErrorBody {
  detail?: string | ReadonlyArray<{ loc: ReadonlyArray<string | number>; msg: string }>;
}

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  timeout: 30_000,
  headers: { Accept: "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = session.getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ErrorBody>) => {
    const status = error.response?.status ?? 0;
    const detail = error.response?.data?.detail;
    const normalized: ApiError = {
      status,
      message:
        typeof detail === "string"
          ? detail
          : status === 0
            ? "تعذر الاتصال بالخادم."
            : "تعذر إكمال الطلب.",
      validation: Array.isArray(detail) ? detail : undefined,
    };
    if (status === 401 && !error.config?.url?.endsWith("/auth/login")) {
      session.clear();
      if (typeof window !== "undefined") window.location.assign("/login");
    }
    return Promise.reject(normalized);
  },
);

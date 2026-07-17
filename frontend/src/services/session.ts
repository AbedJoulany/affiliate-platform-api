const ACCESS_TOKEN_KEY = "affiliate_access_token";

export const session = {
  getAccessToken(): string | null {
    if (typeof window === "undefined") return null;
    return window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
  },
  setAccessToken(token: string): void {
    window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${ACCESS_TOKEN_KEY}=1; Path=/; SameSite=Lax${secure}`;
  },
  clear(): void {
    if (typeof window !== "undefined") window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    if (typeof document !== "undefined") {
      document.cookie = `${ACCESS_TOKEN_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
    }
  },
};

export const SESSION_COOKIE = ACCESS_TOKEN_KEY;

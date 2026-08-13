const ACCESS_TOKEN_KEY = "affiliate_access_token";
const REFRESH_TOKEN_KEY = "affiliate_refresh_token";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export const session = {
  getAccessToken(): string | null {
    if (!isBrowser()) return null;
    return window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
  },
  getRefreshToken(): string | null {
    if (!isBrowser()) return null;
    return window.sessionStorage.getItem(REFRESH_TOKEN_KEY);
  },
  setAccessToken(token: string): void {
    window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${ACCESS_TOKEN_KEY}=1; Path=/; SameSite=Lax${secure}`;
  },
  setRefreshToken(token: string): void {
    window.sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
  },
  setTokens(accessToken: string, refreshToken: string): void {
    this.setAccessToken(accessToken);
    this.setRefreshToken(refreshToken);
  },
  clear(): void {
    if (isBrowser()) {
      window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
      window.sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    }
    if (typeof document !== "undefined") {
      document.cookie = `${ACCESS_TOKEN_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
    }
  },
};

export const SESSION_COOKIE = ACCESS_TOKEN_KEY;

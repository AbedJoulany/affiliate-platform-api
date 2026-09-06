const ACCESS_TOKEN_KEY = "affiliate_access_token";
const REFRESH_TOKEN_KEY = "affiliate_refresh_token";
const ACTIVE_WORKSPACE_KEY = "affiliate_active_workspace_id";

type WorkspaceListener = () => void;

const workspaceListeners = new Set<WorkspaceListener>();

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function notifyWorkspaceListeners(): void {
  workspaceListeners.forEach((listener) => listener());
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
  getActiveWorkspaceId(): string | null {
    if (!isBrowser()) return null;
    return window.sessionStorage.getItem(ACTIVE_WORKSPACE_KEY);
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
  setActiveWorkspaceId(workspaceId: string): void {
    if (!isBrowser()) return;
    window.sessionStorage.setItem(ACTIVE_WORKSPACE_KEY, workspaceId);
    notifyWorkspaceListeners();
  },
  clearActiveWorkspaceId(): void {
    if (isBrowser()) {
      window.sessionStorage.removeItem(ACTIVE_WORKSPACE_KEY);
    }
    notifyWorkspaceListeners();
  },
  subscribeWorkspace(listener: WorkspaceListener): () => void {
    workspaceListeners.add(listener);
    return () => {
      workspaceListeners.delete(listener);
    };
  },
  clear(): void {
    if (isBrowser()) {
      window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
      window.sessionStorage.removeItem(REFRESH_TOKEN_KEY);
      window.sessionStorage.removeItem(ACTIVE_WORKSPACE_KEY);
    }
    if (typeof document !== "undefined") {
      document.cookie = `${ACCESS_TOKEN_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
    }
    notifyWorkspaceListeners();
  },
};

export const SESSION_COOKIE = ACCESS_TOKEN_KEY;

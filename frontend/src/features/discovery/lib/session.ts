import type { DiscoverySessionSnapshot } from "../types/api";
import { normalizeDiscoveryResponse, type DiscoveryResponseRaw } from "./normalize";
import { DEFAULT_UI_PREFS, normalizeUiPrefs } from "./ui-prefs";

const STORAGE_KEY = "affiliate_discovery_session_v1";

const emptySession = (): DiscoverySessionSnapshot => ({
  draftParams: { mode: "hot", sort: "orders_desc", page: 1, page_size: 20 },
  committedParams: null,
  lastResponse: null,
  lastRunAt: null,
  lastRunStatus: "idle",
  lastError: null,
  importedIds: [],
  activeProfileId: null,
  uiPrefs: DEFAULT_UI_PREFS,
});

export function loadDiscoverySession(): DiscoverySessionSnapshot {
  if (typeof window === "undefined") return emptySession();
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return emptySession();
    const parsed = JSON.parse(raw) as DiscoverySessionSnapshot;
    const lastResponse = parsed.lastResponse
      ? normalizeDiscoveryResponse(parsed.lastResponse as unknown as DiscoveryResponseRaw)
      : null;
    return {
      ...emptySession(),
      ...parsed,
      lastResponse,
      uiPrefs: normalizeUiPrefs(parsed.uiPrefs),
    };
  } catch {
    return emptySession();
  }
}

export function saveDiscoverySession(session: DiscoverySessionSnapshot): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearDiscoverySession(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(STORAGE_KEY);
}

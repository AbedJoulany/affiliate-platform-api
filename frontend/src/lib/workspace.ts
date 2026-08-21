import type { QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { session } from "@/services/session";

export const WORKSPACE_HEADER = "X-Workspace-Id";

export const WORKSPACE_SCOPED_QUERY_ROOTS = [
  "queue",
  "channels",
  "dashboard",
] as const;

export type WorkspaceScopedQueryRoot =
  (typeof WORKSPACE_SCOPED_QUERY_ROOTS)[number];

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const WORKSPACE_SCOPED_PREFIXES = [
  "/campaigns",
  "/conversions",
  "/queues",
  "/channels",
  "/dashboard",
] as const;

export function isUsableWorkspaceId(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const trimmed = value.trim();
  if (!trimmed) return false;
  const lowered = trimmed.toLowerCase();
  if (lowered === "undefined" || lowered === "null") return false;
  return UUID_RE.test(trimmed);
}

export function normalizeWorkspaceId(value: unknown): string | null {
  if (!isUsableWorkspaceId(value)) return null;
  return value.trim();
}

export function getActiveWorkspaceId(): string | null {
  const stored = normalizeWorkspaceId(session.getActiveWorkspaceId());
  if (stored) return stored;
  return normalizeWorkspaceId(process.env.NEXT_PUBLIC_WORKSPACE_ID);
}

export function setActiveWorkspaceId(workspaceId: string): void {
  const normalized = normalizeWorkspaceId(workspaceId);
  if (!normalized) {
    session.clearActiveWorkspaceId();
    return;
  }
  session.setActiveWorkspaceId(normalized);
}

export function clearActiveWorkspaceId(): void {
  session.clearActiveWorkspaceId();
}

export function applyDefaultWorkspaceFromUser(user: {
  default_workspace_id?: string | null;
}): void {
  const id = normalizeWorkspaceId(user.default_workspace_id);
  if (id) setActiveWorkspaceId(id);
}

export function subscribeActiveWorkspace(listener: () => void): () => void {
  return session.subscribeWorkspace(listener);
}

export function useActiveWorkspaceId(): string | null {
  return useSyncExternalStore(
    subscribeActiveWorkspace,
    getActiveWorkspaceId,
    () => null,
  );
}

export function requestPathname(url: string | undefined): string {
  if (!url) return "";
  try {
    const parsed =
      url.startsWith("http://") || url.startsWith("https://")
        ? new URL(url)
        : new URL(url, "http://local.invalid");
    return parsed.pathname.replace(/\/+$/, "") || "/";
  } catch {
    return url.replace(/\/+$/, "") || url;
  }
}

/**
 * Tenant-scoped HTTP paths that require `X-Workspace-Id`.
 * Global catalog/auth/affiliate-profile paths must not match.
 */
export function isWorkspaceScopedPath(url: string | undefined): boolean {
  const path = requestPathname(url);
  const normalized = path.startsWith("/api/v1/")
    ? path.slice("/api/v1".length)
    : path;

  if (
    normalized === "/affiliates/join-campaign" ||
    normalized.startsWith("/affiliates/join-campaign/")
  ) {
    return true;
  }

  return WORKSPACE_SCOPED_PREFIXES.some(
    (prefix) => normalized === prefix || normalized.startsWith(`${prefix}/`),
  );
}

export function workspaceScopedQueryKey(
  root: WorkspaceScopedQueryRoot,
  workspaceId: string,
  ...rest: unknown[]
) {
  return [root, workspaceId, ...rest] as const;
}

export function isWorkspaceScopedQueryKey(
  queryKey: readonly unknown[],
): boolean {
  const root = queryKey[0];
  return (
    typeof root === "string" &&
    (WORKSPACE_SCOPED_QUERY_ROOTS as readonly string[]).includes(root)
  );
}

/** Drop tenant cache so workspace B cannot render A's stale rows. */
export function removeWorkspaceScopedQueries(queryClient: QueryClient): void {
  queryClient.removeQueries({
    predicate: (query) => isWorkspaceScopedQueryKey(query.queryKey),
  });
}

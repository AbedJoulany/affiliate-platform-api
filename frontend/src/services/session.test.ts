import { afterEach, describe, expect, it } from "vitest";
import { session } from "./session";
import { getActiveWorkspaceId, setActiveWorkspaceId } from "@/lib/workspace";
import { WORKSPACE_A } from "@/test/workspace";

afterEach(() => {
  session.clear();
});

describe("session token storage", () => {
  it("stores access and refresh tokens independently", () => {
    session.setTokens("access-1", "refresh-1");
    expect(session.getAccessToken()).toBe("access-1");
    expect(session.getRefreshToken()).toBe("refresh-1");
    expect(document.cookie).toContain("affiliate_access_token=1");
    expect(document.cookie).not.toContain("refresh-1");
  });

  it("replaces the refresh token on rotation", () => {
    session.setTokens("access-1", "refresh-1");
    session.setTokens("access-2", "refresh-2");
    expect(session.getAccessToken()).toBe("access-2");
    expect(session.getRefreshToken()).toBe("refresh-2");
  });

  it("clears both tokens and the presence cookie", () => {
    session.setTokens("access-1", "refresh-1");
    setActiveWorkspaceId(WORKSPACE_A);
    session.clear();
    expect(session.getAccessToken()).toBeNull();
    expect(session.getRefreshToken()).toBeNull();
    expect(getActiveWorkspaceId()).toBeNull();
    expect(document.cookie).not.toContain("affiliate_access_token=1");
  });
});

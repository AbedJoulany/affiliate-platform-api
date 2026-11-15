import { describe, expect, it } from "vitest";
import {
  getQueueDestination,
  isAmbiguousFacebookAttempt,
  queueProvider,
} from "./destination";

const base = {
  provider: "telegram" as const,
  channel_id: "channel-1",
  facebook_page_id: null,
};

describe("queue destination display", () => {
  it("keeps legacy rows as Telegram", () => {
    const item = { ...base, provider: undefined };
    expect(queueProvider(item)).toBe("telegram");
    expect(getQueueDestination(item)).toMatchObject({
      provider: "telegram",
      label: "Telegram",
      identity: "channel-1",
      available: false,
    });
  });

  it("displays a validated Facebook Page without exposing credentials", () => {
    const item = {
      ...base,
      provider: "facebook" as const,
      channel_id: null,
      facebook_page_id: "page-row-1",
    };
    const page = {
      id: "page-row-1",
      workspace_id: "workspace-1",
      facebook_page_id: "123456",
      page_name: "Test Page",
      token_expires_at: null,
      is_active: true,
      validation_status: "valid" as const,
      last_validated_at: null,
      last_error: null,
      has_access_token: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const destination = getQueueDestination(item, null, page);
    expect(destination).toMatchObject({
      provider: "facebook",
      label: "Facebook",
      name: "Test Page",
      identity: "123456",
      available: true,
    });
    expect(JSON.stringify(destination)).not.toContain("token");
  });

  it("marks inaccessible destinations unavailable", () => {
    const destination = getQueueDestination(
      { ...base, provider: "facebook", channel_id: null, facebook_page_id: "row" },
      null,
      null,
    );
    expect(destination.available).toBe(false);
    expect(destination.identity).toBe("row");
  });
});
describe("ambiguous Facebook attempts", () => {
  it("only treats the Facebook ambiguous attempt as uncertain", () => {
    expect(
      isAmbiguousFacebookAttempt(
        { provider: "facebook" },
        { provider: "facebook", status: "ambiguous" },
      ),
    ).toBe(true);
    expect(
      isAmbiguousFacebookAttempt(
        { provider: "telegram" },
        { provider: "facebook", status: "ambiguous" },
      ),
    ).toBe(false);
  });
});

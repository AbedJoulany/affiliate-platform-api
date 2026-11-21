import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/services/api-client";
import { getAutomationPolicy } from "./automation.api";

vi.mock("@/services/api-client", () => ({
  apiClient: { get: vi.fn(), patch: vi.fn() },
}));

const getMock = vi.mocked(apiClient.get);

afterEach(() => vi.clearAllMocks());

describe("automation API contract validation", () => {
  it("rejects a malformed policy response instead of rendering invented defaults", async () => {
    getMock.mockResolvedValue({ data: { enabled: false } } as never);
    await expect(getAutomationPolicy()).rejects.toThrow("استجابة إعدادات الأتمتة غير صالحة");
  });
});

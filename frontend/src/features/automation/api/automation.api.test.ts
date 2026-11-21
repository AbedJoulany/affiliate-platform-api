import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/services/api-client";
import { WORKSPACE_A } from "@/test/workspace";
import { getAutomationPolicy, patchAutomationPolicy } from "./automation.api";

vi.mock("@/services/api-client", () => ({
  apiClient: { get: vi.fn(), patch: vi.fn() },
}));

const getMock = vi.mocked(apiClient.get);
const patchMock = vi.mocked(apiClient.patch);

afterEach(() => vi.clearAllMocks());

describe("automation API contract validation", () => {
  it("rejects a malformed policy response instead of rendering invented defaults", async () => {
    getMock.mockResolvedValue({ data: { enabled: false } } as never);
    await expect(getAutomationPolicy(WORKSPACE_A)).rejects.toThrow("استجابة إعدادات الأتمتة غير صالحة");
  });

  it("binds GET and PATCH calls to their captured workspace", async () => {
    const response = {
      workspace_id: WORKSPACE_A,
      revision: 0,
      enabled: false,
      execution_available: false,
      execution_state: "disabled",
      destination: null,
      discovery: {},
      schedule: {},
      content: {},
      warnings: [],
    };
    getMock.mockResolvedValue({ data: response } as never);
    patchMock.mockResolvedValue({ data: response } as never);

    await getAutomationPolicy(WORKSPACE_A);
    await patchAutomationPolicy(WORKSPACE_A, { expected_revision: 0 });

    expect(getMock).toHaveBeenCalledWith("/automation/config", { workspaceId: WORKSPACE_A });
    expect(patchMock).toHaveBeenCalledWith(
      "/automation/config",
      { expected_revision: 0 },
      { workspaceId: WORKSPACE_A },
    );
  });
});

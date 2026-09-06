import { describe, expect, it } from "vitest";
import { getApiErrorMessage } from "./api-client";

describe("getApiErrorMessage", () => {
  it("reads message from a plain ApiError object", () => {
    expect(
      getApiErrorMessage({ status: 403, message: "Insufficient permissions" }, "fallback"),
    ).toBe("Insufficient permissions");
  });

  it("reads message from an Error instance", () => {
    expect(getApiErrorMessage(new Error("boom"), "fallback")).toBe("boom");
  });

  it("uses the fallback when the value is not an error", () => {
    expect(getApiErrorMessage("nope", "تعذر الاستيراد.")).toBe("تعذر الاستيراد.");
    expect(getApiErrorMessage({ status: 500, message: "" }, "تعذر الاستيراد.")).toBe(
      "تعذر الاستيراد.",
    );
  });
});

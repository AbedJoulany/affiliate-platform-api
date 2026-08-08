import { describe, expect, it } from "vitest";
import { estimateCommissionValue, getScoreQuality } from "./score-explanation";

describe("getScoreQuality", () => {
  it("maps score bands for presentation", () => {
    expect(getScoreQuality(92).key).toBe("excellent");
    expect(getScoreQuality(78).key).toBe("high");
    expect(getScoreQuality(64).key).toBe("moderate");
    expect(getScoreQuality(40).key).toBe("low");
  });
});

describe("estimateCommissionValue", () => {
  it("computes value from price and rate", () => {
    expect(estimateCommissionValue(100, 8)).toBe(8);
    expect(estimateCommissionValue(19.99, null)).toBeNull();
  });
});

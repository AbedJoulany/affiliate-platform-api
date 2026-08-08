import { describe, expect, it } from "vitest";
import { createEmptySession } from "./session";

describe("createEmptySession", () => {
  it("returns a clean ready-to-generate session", () => {
    const session = createEmptySession();
    expect(session.variants).toEqual([]);
    expect(session.activeVariantId).toBeNull();
    expect(session.productContext.productId).toBeNull();
    expect(session.productContext.url).toBe("");
    expect(session.config.language).toBe("ar");
    expect(session.config.length).toBe("medium");
    expect(session.prompt.instructionModifiers).toEqual([]);
    expect(session.advancedOpen).toBe(false);
    expect(session.suggestionsOpen).toBe(false);
  });
});

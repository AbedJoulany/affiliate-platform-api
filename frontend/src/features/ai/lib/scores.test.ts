import { describe, expect, it } from "vitest";
import { scoreContent } from "./scores";

describe("scoreContent", () => {
  it("scores Arabic marketing copy with CTA and URL higher", () => {
    const content = `
## عرض خاص
احصل على سماعات لاسلكية الآن.
اشتري الآن من الرابط:
https://example.com/product
`;
    const scores = scoreContent(content, "ar");
    expect(scores.arabic).toBeGreaterThan(50);
    expect(scores.marketing).toBeGreaterThan(60);
    expect(scores.seo).toBeGreaterThan(40);
    expect(scores.readability).toBeGreaterThan(40);
  });
});

import { describe, expect, it } from "vitest";
import { parseMarketingDocument, serializeDocument } from "./document";

describe("parseMarketingDocument", () => {
  it("parses headings, lists, and CTA blocks", () => {
    const blocks = parseMarketingDocument(`## عنوان
فقرة تعريفية.

- ميزة أولى
- ميزة ثانية

اشتري الآن
https://example.com/p
`);
    expect(blocks.some((block) => block.type === "heading")).toBe(true);
    expect(blocks.some((block) => block.type === "unordered_list")).toBe(true);
    expect(blocks.some((block) => block.type === "cta")).toBe(true);
    expect(serializeDocument(blocks)).toContain("عنوان");
  });
});

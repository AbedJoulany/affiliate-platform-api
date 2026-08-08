import type { DocumentBlock } from "../types/session";

/** Lightweight markdown-ish parse for the Notion-style canvas. */
export function parseMarketingDocument(content: string): DocumentBlock[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: DocumentBlock[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listType: "unordered_list" | "ordered_list" | null = null;

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    const text = paragraph.join(" ").trim();
    if (text) blocks.push({ type: "paragraph", text });
    paragraph = [];
  };

  const flushList = () => {
    if (!listType || listItems.length === 0) {
      listItems = [];
      listType = null;
      return;
    }
    blocks.push({ type: listType, items: [...listItems] });
    listItems = [];
    listType = null;
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    if (/^#{2}\s+/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", level: 2, text: line.replace(/^#{2}\s+/, "") });
      continue;
    }
    if (/^#{3}\s+/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", level: 3, text: line.replace(/^#{3}\s+/, "") });
      continue;
    }

    const unordered = line.match(/^[-*•]\s+(.+)/);
    if (unordered) {
      flushParagraph();
      if (listType && listType !== "unordered_list") flushList();
      listType = "unordered_list";
      listItems.push(unordered[1]);
      continue;
    }

    const ordered = line.match(/^\d+[.)]\s+(.+)/);
    if (ordered) {
      flushParagraph();
      if (listType && listType !== "ordered_list") flushList();
      listType = "ordered_list";
      listItems.push(ordered[1]);
      continue;
    }

    const ctaLike =
      /^(CTA|حث|اضغط|اشتري|اشترِ|اطلب الآن|Shop now)/i.test(line) ||
      (line.includes("http") && line.length < 180);
    if (ctaLike) {
      flushParagraph();
      flushList();
      const urlMatch = line.match(/https?:\/\/\S+/);
      blocks.push({
        type: "cta",
        text: line.replace(/https?:\/\/\S+/g, "").trim() || line,
        url: urlMatch?.[0],
      });
      continue;
    }

    if (listType) flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  return blocks.length > 0 ? blocks : [{ type: "paragraph", text: content.trim() }];
}

export function serializeDocument(blocks: DocumentBlock[]): string {
  return blocks
    .map((block) => {
      switch (block.type) {
        case "heading":
          return `${"#".repeat(block.level)} ${block.text}`;
        case "paragraph":
          return block.text;
        case "unordered_list":
          return block.items.map((item) => `- ${item}`).join("\n");
        case "ordered_list":
          return block.items.map((item, index) => `${index + 1}. ${item}`).join("\n");
        case "cta":
          return block.url ? `${block.text}\n${block.url}` : block.text;
        default:
          return "";
      }
    })
    .filter(Boolean)
    .join("\n\n");
}

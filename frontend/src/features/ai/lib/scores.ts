import type { PerformanceScores } from "../types/session";

const ARABIC_RE = /[\u0600-\u06FF]/g;
const CTA_RE = /(اشتري|اشترِ|اطلب|shop|buy|order|اكتشف|shop now|اضغط)/i;
const URL_RE = /https?:\/\/\S+/i;
const HEADING_RE = /^#{1,3}\s+.+/m;

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

/** Client-side heuristic scores until a dedicated scoring API exists. */
export function scoreContent(content: string, language: string): PerformanceScores {
  const text = content.trim();
  if (!text) {
    return { arabic: 0, marketing: 0, seo: 0, readability: 0 };
  }

  const letters = text.replace(/\s/g, "");
  const arabicChars = (text.match(ARABIC_RE) ?? []).join("").length;
  const arabicRatio = letters.length ? arabicChars / letters.length : 0;

  const arabic =
    language === "ar"
      ? clampScore(arabicRatio * 100)
      : clampScore(100 - arabicRatio * 80);

  let marketing = 40;
  if (CTA_RE.test(text)) marketing += 25;
  if (URL_RE.test(text)) marketing += 20;
  if ((text.match(/[!！]/g) ?? []).length > 0) marketing += 5;
  if (text.length > 120) marketing += 10;

  let seo = 35;
  if (HEADING_RE.test(text) || text.includes("\n\n")) seo += 20;
  const words = text.split(/\s+/).filter(Boolean);
  const unique = new Set(words.map((word) => word.toLowerCase()));
  if (words.length > 0) seo += Math.min(25, (unique.size / words.length) * 40);
  if (text.length >= 80 && text.length <= 800) seo += 15;

  const sentences = text.split(/[.!?؟\n]+/).filter((part) => part.trim().length > 0);
  const avgWords =
    sentences.length > 0 ? words.length / sentences.length : words.length;
  let readability = 70;
  if (avgWords > 28) readability -= 20;
  if (avgWords < 8) readability -= 10;
  if (text.includes("\n")) readability += 10;
  if (words.length >= 40 && words.length <= 400) readability += 10;

  return {
    arabic: clampScore(arabic),
    marketing: clampScore(marketing),
    seo: clampScore(seo),
    readability: clampScore(readability),
  };
}

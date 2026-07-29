import type {
  AIProvider,
  ContentLanguage,
  ContentLength,
  ContentType,
  InstructionModifier,
  ToneProfile,
} from "./api";

export type DocumentBlock =
  | { type: "heading"; level: 2 | 3; text: string }
  | { type: "paragraph"; text: string }
  | { type: "unordered_list"; items: string[] }
  | { type: "ordered_list"; items: string[] }
  | { type: "cta"; text: string; url?: string };

export interface PerformanceScores {
  arabic: number;
  marketing: number;
  seo: number;
  readability: number;
}

export interface SessionConfig {
  contentType: ContentType;
  tone: ToneProfile;
  language: ContentLanguage;
  length: ContentLength;
  /** null/undefined = system default provider */
  provider?: AIProvider | null;
}

export interface ProductContextState {
  sourceType: "product" | "url";
  productId: string | null;
  productLabel: string | null;
  url: string | null;
}

export type ContentVariantOrigin = "generate" | "variant" | "restore" | "manual_edit";

export interface ContentVariant {
  id: string;
  index: number;
  createdAt: string;
  content: string;
  structured?: DocumentBlock[];
  scores: PerformanceScores;
  configSnapshot: SessionConfig;
  modifiersSnapshot: InstructionModifier[];
  provider: AIProvider | null;
  productId: string | null;
  sourceUrl: string | null;
  origin: ContentVariantOrigin;
}

export type ContentSessionEvent =
  | { type: "session_created"; at: string }
  | { type: "config_changed"; at: string; config: SessionConfig }
  | {
      type: "modifier_toggled";
      at: string;
      modifier: InstructionModifier;
      enabled: boolean;
    }
  | { type: "variant_generated"; at: string; variantId: string }
  | { type: "variant_activated"; at: string; variantId: string }
  | {
      type: "variant_restored";
      at: string;
      fromVariantId: string;
      newVariantId: string;
    }
  | {
      type: "exported" | "queued" | "published" | "draft_saved";
      at: string;
      variantId: string;
    };

export interface ContentSession {
  id: string;
  createdAt: string;
  updatedAt: string;
  productContext: ProductContextState;
  config: SessionConfig;
  prompt: {
    instructionModifiers: InstructionModifier[];
  };
  variants: ContentVariant[];
  activeVariantId: string | null;
  history: ContentSessionEvent[];
  suggestionsOpen: boolean;
  advancedOpen: boolean;
  compareVariantIds: [string, string] | null;
}

export const CONTENT_TYPE_OPTIONS: ReadonlyArray<{ value: ContentType; label: string }> = [
  { value: "social", label: "منشور شبكات" },
  { value: "description", label: "وصف منتج" },
  { value: "telegram", label: "منشور تلغرام" },
  { value: "facebook", label: "إعلان فيسبوك" },
  { value: "blog", label: "مقال مدونة" },
  { value: "email", label: "بريد إلكتروني" },
];

export const TONE_OPTIONS: ReadonlyArray<{ value: ToneProfile; label: string }> = [
  { value: "professional", label: "مهني" },
  { value: "friendly", label: "ودي" },
  { value: "luxury", label: "فاخر" },
  { value: "technical", label: "تقني" },
  { value: "urgent", label: "عاجل" },
  { value: "minimal", label: "بسيط" },
  { value: "persuasive", label: "إقناعي" },
  { value: "funny", label: "فكاهي" },
];

export const LANGUAGE_OPTIONS: ReadonlyArray<{ value: ContentLanguage; label: string }> = [
  { value: "ar", label: "العربية" },
  { value: "en", label: "English" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
];

export const LENGTH_OPTIONS: ReadonlyArray<{ value: ContentLength; label: string }> = [
  { value: "short", label: "قصير" },
  { value: "medium", label: "متوسط" },
  { value: "long", label: "طويل" },
];

export const MODIFIER_OPTIONS: ReadonlyArray<{
  value: InstructionModifier;
  label: string;
}> = [
  { value: "add_emojis", label: "إضافة رموز تعبيرية" },
  { value: "strengthen_cta", label: "تقوية عبارة CTA" },
  { value: "shorten", label: "تقصير النص" },
  { value: "increase_urgency", label: "زيادة طابع العجلة" },
  { value: "improve_seo", label: "تحسين الـ SEO" },
];

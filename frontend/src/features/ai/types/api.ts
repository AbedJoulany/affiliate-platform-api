export type AIProvider = "openai" | "gemini";

export type ContentType =
  | "social"
  | "description"
  | "telegram"
  | "facebook"
  | "blog"
  | "email";

export type ToneProfile =
  | "professional"
  | "friendly"
  | "luxury"
  | "technical"
  | "urgent"
  | "minimal"
  | "persuasive"
  | "funny";

export type ContentLanguage = "ar" | "en" | "fr" | "de";
export type ContentLength = "short" | "medium" | "long";

export type InstructionModifier =
  | "add_emojis"
  | "strengthen_cta"
  | "shorten"
  | "increase_urgency"
  | "improve_seo";

export type GenerateContentInput = {
  provider?: AIProvider;
  content_type?: ContentType;
  tone?: ToneProfile;
  language?: ContentLanguage;
  length?: ContentLength;
  instruction_modifiers?: InstructionModifier[];
} & (
  | { product_id: string; url?: never }
  | { url: string; product_id?: never }
);

export interface GenerateContentResponse {
  product_id: string | null;
  source_url: string | null;
  provider: AIProvider;
  content: string;
  content_type: ContentType;
  tone: ToneProfile;
  language: ContentLanguage;
  length: ContentLength;
}

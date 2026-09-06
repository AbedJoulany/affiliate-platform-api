import { z } from "zod";
import { invalidUuid, requiredField } from "@/lib/validation/messages";

export const TIMEZONES = [
  "UTC",
  "Asia/Jerusalem",
  "Asia/Riyadh",
  "Asia/Dubai",
  "Africa/Cairo",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "America/New_York",
  "America/Los_Angeles",
] as const;

export const UI_LANGUAGES = ["ar", "en"] as const;
export const AI_PROVIDERS = ["openai", "gemini"] as const;
export const CONTENT_TYPES = [
  "social",
  "description",
  "telegram",
  "facebook",
  "blog",
  "email",
] as const;
export const TONE_PROFILES = [
  "professional",
  "friendly",
  "luxury",
  "technical",
  "urgent",
  "minimal",
  "persuasive",
  "funny",
] as const;
export const CONTENT_LANGUAGES = ["ar", "en", "fr", "de"] as const;
export const CONTENT_LENGTHS = ["short", "medium", "long"] as const;
export const DISCOVERY_MODES = [
  "general",
  "hot",
  "deals",
  "trending",
  "category",
] as const;

export const workspaceGeneralSchema = z.object({
  timezone: z.enum(TIMEZONES, {
    message: requiredField("المنطقة الزمنية", { feminine: true }),
  }),
  ui_language: z.enum(UI_LANGUAGES),
});

export const aliexpressDisplaySchema = z.object({
  aliexpress_target_currency: z
    .string()
    .min(3, requiredField("العملة"))
    .max(3)
    .regex(/^[A-Za-z]{3}$/, "أدخل رمز عملة من ثلاثة أحرف"),
  aliexpress_ship_to_country: z
    .string()
    .min(2, requiredField("بلد الشحن"))
    .max(2)
    .regex(/^[A-Za-z]{2}$/, "أدخل رمز بلد من حرفين"),
  aliexpress_target_language: z
    .string()
    .min(2, requiredField("لغة العرض", { feminine: true }))
    .max(8),
});

export const aiDefaultsSchema = z.object({
  default_ai_provider: z.enum(AI_PROVIDERS),
  default_content_type: z.enum(CONTENT_TYPES),
  default_tone: z.enum(TONE_PROFILES),
  default_content_language: z.enum(CONTENT_LANGUAGES),
  default_content_length: z.enum(CONTENT_LENGTHS),
});

export const telegramDefaultsSchema = z.object({
  default_telegram_channel_id: z
    .string()
    .refine((value) => value === "" || z.string().uuid().safeParse(value).success, {
      message: invalidUuid("معرّف القناة"),
    }),
});

export const discoveryDefaultsSchema = z.object({
  discovery_default_mode: z.enum(DISCOVERY_MODES),
  discovery_page_size: z.number().int().min(1).max(50),
});

export const schedulingDefaultsSchema = z.object({
  timezone: z.enum(TIMEZONES, {
    message: requiredField("المنطقة الزمنية", { feminine: true }),
  }),
});

export type WorkspaceGeneralValues = z.infer<typeof workspaceGeneralSchema>;
export type AliExpressDisplayValues = z.infer<typeof aliexpressDisplaySchema>;
export type AiDefaultsValues = z.infer<typeof aiDefaultsSchema>;
export type TelegramDefaultsValues = z.infer<typeof telegramDefaultsSchema>;
export type DiscoveryDefaultsValues = z.infer<typeof discoveryDefaultsSchema>;
export type SchedulingDefaultsValues = z.infer<typeof schedulingDefaultsSchema>;


import { z } from "zod";

const optionalDecimal = (label: string, max?: number) =>
  z
    .string()
    .trim()
    .refine(
      (value) => value === "" || /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value),
      `${label}: أدخل رقماً صحيحاً`,
    )
    .refine(
      (value) =>
        value === "" || (max === undefined ? true : Number(value) <= max),
      `${label}: القيمة خارج النطاق`,
    );

const optionalInteger = (label: string) =>
  z
    .string()
    .trim()
    .refine(
      (value) => value === "" || /^(?:0|[1-9]\d*)$/.test(value),
      `${label}: أدخل عدداً صحيحاً`,
    );

export const automationFormSchema = z
  .object({
    enabled: z.boolean(),
    destination_provider: z.enum(["", "telegram", "facebook"]),
    destination_id: z.string(),
    keywords: z.string().max(255, "الكلمات المفتاحية يجب ألا تتجاوز 255 حرفاً"),
    min_price: optionalDecimal("الحد الأدنى للسعر"),
    max_price: optionalDecimal("الحد الأعلى للسعر"),
    min_rating: optionalDecimal("الحد الأدنى للتقييم", 5),
    min_orders: optionalInteger("الحد الأدنى للطلبات"),
    min_discount: optionalDecimal("الحد الأدنى للخصم", 100),
    min_commission: optionalDecimal("الحد الأدنى للعمولة", 100),
    max_commission: optionalDecimal("الحد الأعلى للعمولة", 100),
    products_per_run: z.number().int("أدخل عدداً صحيحاً").min(1).max(50),
    frequency: z.literal("daily"),
    preferred_time_local: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, "استخدم صيغة HH:MM"),
    posts_per_day: z.number().int("أدخل عدداً صحيحاً").min(1).max(10),
    ai_provider: z.enum(["", "openai", "gemini"]),
    language: z.enum(["", "ar", "en", "fr", "de"]),
    tone: z.enum([
      "",
      "professional",
      "friendly",
      "luxury",
      "technical",
      "urgent",
      "minimal",
      "persuasive",
      "funny",
    ]),
    content_type: z.enum(["", "social", "description", "telegram", "facebook", "blog", "email"]),
    length: z.enum(["", "short", "medium", "long"]),
  })
  .superRefine((values, context) => {
    if (values.enabled && (!values.destination_provider || !values.destination_id)) {
      context.addIssue({
        code: "custom",
        path: ["destination_id"],
        message: "اختر وجهة نشر صالحة قبل تفعيل الرغبة في الأتمتة",
      });
    }
    if (
      values.min_price &&
      values.max_price &&
      Number(values.min_price) > Number(values.max_price)
    ) {
      context.addIssue({
        code: "custom",
        path: ["max_price"],
        message: "يجب ألا يتجاوز الحد الأدنى الحد الأعلى",
      });
    }
    if (
      values.min_commission &&
      values.max_commission &&
      Number(values.min_commission) > Number(values.max_commission)
    ) {
      context.addIssue({
        code: "custom",
        path: ["max_commission"],
        message: "يجب ألا تتجاوز العمولة الدنيا العمولة القصوى",
      });
    }
  });

export type AutomationFormValues = z.infer<typeof automationFormSchema>;

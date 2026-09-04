import { z } from "zod";
import { requiredField } from "@/lib/validation/messages";

export const profileSchema = z.object({
  full_name: z.string().min(1, requiredField("الاسم الكامل")),
  email: z.string().min(1, requiredField("البريد الإلكتروني")).email("أدخل بريداً إلكترونياً صالحاً"),
});

export type ProfileFormValues = z.infer<typeof profileSchema>;

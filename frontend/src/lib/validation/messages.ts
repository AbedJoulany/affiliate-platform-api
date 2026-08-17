/**
 * Small Arabic Zod validation-message helpers.
 * Not an i18n system — preserves existing copy used by Tasks 1–4 schemas.
 */

export function requiredField(
  label: string,
  options?: { feminine?: boolean },
): string {
  return `${label} ${options?.feminine ? "مطلوبة" : "مطلوب"}`;
}

export function invalidUuid(label: string): string {
  return `${label} غير صالح`;
}

export const invalidDateTime = "أدخل تاريخًا ووقتًا صحيحين";

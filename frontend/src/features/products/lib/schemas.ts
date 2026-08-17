import { z } from "zod";
import { PRODUCT_STATUSES, type ProductStatus } from "../types/api";

/** Reuses the existing product status source of truth from `types/api.ts`. */
export const productStatusSchema = z.enum(PRODUCT_STATUSES);

export const productStatusLabels: Record<ProductStatus, string> = {
  draft: "مسودة",
  active: "نشط",
  inactive: "غير نشط",
  archived: "مؤرشف",
};

export const productStatusOptions = PRODUCT_STATUSES.map((value) => ({
  value,
  label: productStatusLabels[value],
}));

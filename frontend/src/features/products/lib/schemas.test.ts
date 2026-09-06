import { describe, expect, it } from "vitest";
import { z } from "zod";
import type { ProductStatus } from "../types/api";
import { PRODUCT_STATUSES } from "../types/api";
import {
  productStatusLabels,
  productStatusOptions,
  productStatusSchema,
} from "./schemas";

type InferredProductStatus = z.infer<typeof productStatusSchema>;
type StatusesCompatible = InferredProductStatus extends ProductStatus
  ? ProductStatus extends InferredProductStatus
    ? true
    : false
  : false;

describe("productStatusSchema", () => {
  it("accepts every existing product status", () => {
    for (const status of PRODUCT_STATUSES) {
      const result = productStatusSchema.safeParse(status);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toBe(status);
      }
    }
  });

  it("rejects an unsupported status", () => {
    expect(productStatusSchema.safeParse("queued").success).toBe(false);
    expect(productStatusSchema.safeParse("published").success).toBe(false);
    expect(productStatusSchema.safeParse("").success).toBe(false);
    expect(productStatusSchema.safeParse("ACTIVE").success).toBe(false);
  });

  it("keeps the inferred type compatible with ProductStatus", () => {
    const compatible: StatusesCompatible = true;
    expect(compatible).toBe(true);
    expect(PRODUCT_STATUSES).toEqual(["draft", "active", "inactive", "archived"]);
  });
});

describe("product status labels and options", () => {
  it("preserves the existing Arabic labels", () => {
    expect(productStatusLabels).toEqual({
      draft: "مسودة",
      active: "نشط",
      inactive: "غير نشط",
      archived: "مؤرشف",
    });
  });

  it("exposes one option per valid status in the existing UI order", () => {
    expect(productStatusOptions.map((option) => option.value)).toEqual([
      ...PRODUCT_STATUSES,
    ]);
    expect(productStatusOptions.map((option) => option.label)).toEqual([
      "مسودة",
      "نشط",
      "غير نشط",
      "مؤرشف",
    ]);
  });

  it("does not include duplicate or invalid option values", () => {
    const values = productStatusOptions.map((option) => option.value);
    expect(new Set(values).size).toBe(values.length);
    for (const value of values) {
      expect(productStatusSchema.safeParse(value).success).toBe(true);
    }
  });
});

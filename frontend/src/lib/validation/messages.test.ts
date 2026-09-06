import { describe, expect, it } from "vitest";
import { invalidDateTime, invalidUuid, requiredField } from "./messages";
import { channelAssignmentSchema } from "@/features/queue/lib/schemas";

describe("Arabic validation message helper", () => {
  it("preserves existing required-field copy", () => {
    expect(requiredField("القناة المستهدفة", { feminine: true })).toBe(
      "القناة المستهدفة مطلوبة",
    );
    expect(requiredField("تاريخ ووقت الجدولة")).toBe(
      "تاريخ ووقت الجدولة مطلوب",
    );
  });

  it("preserves existing invalid UUID copy", () => {
    expect(invalidUuid("معرّف القناة")).toBe("معرّف القناة غير صالح");
  });

  it("preserves existing invalid date/time copy", () => {
    expect(invalidDateTime).toBe("أدخل تاريخًا ووقتًا صحيحين");
  });

  it("is consumed by channelAssignmentSchema without changing messages", () => {
    const empty = channelAssignmentSchema.safeParse("");
    expect(empty.success).toBe(false);
    if (!empty.success) {
      expect(empty.error.issues[0]?.message).toBe(
        requiredField("القناة المستهدفة", { feminine: true }),
      );
    }

    const invalid = channelAssignmentSchema.safeParse("not-a-uuid");
    expect(invalid.success).toBe(false);
    if (!invalid.success) {
      expect(invalid.error.issues[0]?.message).toBe(invalidUuid("معرّف القناة"));
    }
  });
});

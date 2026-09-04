import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { isApiError } from "@/services/api-client";

export function applyApiFieldErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  allowedFields: ReadonlyArray<Path<T>>,
): boolean {
  if (!isApiError(error) || error.validation == null) {
    return false;
  }
  const allowed = new Set(allowedFields.map(String));
  let mapped = false;
  for (const item of error.validation) {
    const name = item.loc.filter((part) => part !== "body").at(-1);
    if (typeof name === "string" && allowed.has(name)) {
      setError(name as Path<T>, { type: "server", message: item.msg });
      mapped = true;
    }
  }
  return mapped;
}

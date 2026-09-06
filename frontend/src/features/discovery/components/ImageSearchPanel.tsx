"use client";

import { useState } from "react";
import { ImageIcon } from "lucide-react";
import { Button, Input } from "@/components/ui/primitives";
import type { ProductImageSearchRequest } from "../types/api";

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

function isHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error("تعذر قراءة الملف."));
    reader.readAsDataURL(file);
  });
}

export function ImageSearchPanel({
  searching,
  onSearch,
}: {
  searching: boolean;
  onSearch: (payload: ProductImageSearchRequest, file?: File) => void;
}) {
  const [imageUrl, setImageUrl] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const submitUrl = () => {
    const trimmed = imageUrl.trim();
    if (!trimmed) {
      setLocalError("أدخل رابط صورة أو ارفع ملفًا.");
      return;
    }
    if (!isHttpUrl(trimmed)) {
      setLocalError("أدخل رابط صورة صالحًا.");
      return;
    }
    setLocalError(null);
    onSearch({ image_url: trimmed, page: 1, page_size: 20 });
  };

  const submitFile = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setLocalError("ارفع ملف صورة فقط.");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setLocalError("حجم الصورة أكبر من 5MB.");
      return;
    }
    setLocalError(null);
    const image_base64 = await readFileAsBase64(file);
    onSearch({ image_base64, page: 1, page_size: 20 }, file);
  };

  return (
    <section
      className="rounded-lg border border-border bg-surface p-3"
      aria-label="بحث صور المنتجات"
    >
      <div className="flex items-start gap-2">
        <ImageIcon className="mt-1 size-4 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-medium">بحث بالصورة</p>
          <p className="text-sm text-muted-foreground">
            الصق رابط صورة أو ارفع ملفًا للعثور على منتجات مشابهة في الكتالوج العالمي.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              type="url"
              value={imageUrl}
              placeholder="https://example.com/product.jpg"
              aria-label="رابط الصورة"
              onChange={(event) => setImageUrl(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  submitUrl();
                }
              }}
            />
            <Button type="button" disabled={searching} loading={searching} onClick={submitUrl}>
              بحث بالصورة
            </Button>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">
              أو ارفع صورة
              <Input
                className="mt-1"
                type="file"
                accept="image/*"
                aria-label="رفع صورة"
                disabled={searching}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  void submitFile(file);
                  event.target.value = "";
                }}
              />
            </label>
          </div>
          {localError && (
            <p className="text-sm text-destructive" role="alert">
              {localError}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

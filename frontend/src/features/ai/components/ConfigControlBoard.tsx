"use client";

import { Card, Collapsible, Select } from "@/components/ui/primitives";
import type { AIProvider, ContentLanguage, ContentLength, ContentType, ToneProfile } from "../types/api";
import type { ContentSession } from "../types/session";
import { LANGUAGE_OPTIONS, LENGTH_OPTIONS } from "../types/session";
import { ContentTypeScroller } from "./ContentTypeScroller";
import { ProductSourcePicker } from "./ProductSourcePicker";
import { PromptPipelinePreview } from "./PromptPipelinePreview";
import { ToneMatrix } from "./ToneMatrix";

export function ConfigControlBoard({
  session,
  error,
  onProductContextChange,
  onConfigChange,
  onToggleAdvanced,
}: {
  session: ContentSession;
  error?: string | null;
  onProductContextChange: Parameters<typeof ProductSourcePicker>[0]["onChange"];
  onConfigChange: (patch: Partial<ContentSession["config"]>) => void;
  onToggleAdvanced: () => void;
}) {
  return (
    <Card className="space-y-5" aria-label="لوحة إعدادات المحتوى">
      <div>
        <h2 className="font-semibold">لوحة التحكم</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          اضبط المصدر والمنصة والنبرة قبل التوليد.
        </p>
      </div>

      <ProductSourcePicker
        key={session.id}
        value={session.productContext}
        onChange={onProductContextChange}
      />

      <ContentTypeScroller
        value={session.config.contentType}
        onChange={(contentType: ContentType) => onConfigChange({ contentType })}
      />

      <ToneMatrix
        value={session.config.tone}
        onChange={(tone: ToneProfile) => onConfigChange({ tone })}
      />

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1.5 block text-sm" htmlFor="ai-language">
            لغة المحتوى
          </label>
          <Select
            id="ai-language"
            value={session.config.language}
            onChange={(event) =>
              onConfigChange({ language: event.target.value as ContentLanguage })
            }
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <label className="mb-1.5 block text-sm" htmlFor="ai-length">
            طول المحتوى
          </label>
          <Select
            id="ai-length"
            value={session.config.length}
            onChange={(event) =>
              onConfigChange({ length: event.target.value as ContentLength })
            }
          >
            {LENGTH_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <Collapsible
        open={session.advancedOpen}
        title="الإعدادات المتقدمة"
        onToggle={onToggleAdvanced}
      >
        <label className="mb-1.5 block text-sm" htmlFor="ai-provider">
          مزوّد الذكاء الاصطناعي
        </label>
        <Select
          id="ai-provider"
          value={session.config.provider ?? ""}
          onChange={(event) =>
            onConfigChange({
              provider: (event.target.value || null) as AIProvider | null,
            })
          }
        >
          <option value="">الافتراضي من إعدادات النظام</option>
          <option value="openai">OpenAI</option>
          <option value="gemini">Gemini</option>
        </Select>
        <p className="mt-2 text-xs text-muted-foreground">
          اتركه على الافتراضي ما لم تحتج تجاوز مزوّد النظام.
        </p>
      </Collapsible>

      <PromptPipelinePreview session={session} />

      {error ? (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <p className="text-xs text-muted-foreground">
        استخدم شريط الإجراءات أدناه لإنشاء المحتوى أو إعادة التعيين.
      </p>
    </Card>
  );
}

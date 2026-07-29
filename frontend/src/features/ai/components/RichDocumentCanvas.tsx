"use client";

import { useEffect, useState } from "react";
import { parseMarketingDocument } from "../lib/document";
import type { DocumentBlock } from "../types/session";

export function RichDocumentCanvas({
  content,
  onChange,
  placeholder,
}: {
  content: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState(content);
  const blocks = parseMarketingDocument(draft || "");

  useEffect(() => {
    setDraft(content);
  }, [content]);

  if (!draft.trim()) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-muted/20 px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          {placeholder ?? "سيظهر المحتوى هنا كمستند قابل للتحرير بعد التوليد."}
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
      <div className="border-b border-border bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
        مساحة المستند — عدّل النص أدناه؛ العرض المنظّم يتحدث تلقائيًا
      </div>
      <article className="space-y-5 px-6 py-8 sm:px-10" dir="rtl">
        {blocks.map((block, index) => (
          <BlockView key={`${block.type}-${index}`} block={block} />
        ))}
      </article>
      <div className="border-t border-border p-4">
        <label className="mb-1.5 block text-xs text-muted-foreground" htmlFor="ai-doc-editor">
          تحرير النص الخام
        </label>
        <textarea
          id="ai-doc-editor"
          className="min-h-[220px] w-full resize-y rounded-md border border-border bg-background p-4 text-sm leading-8 outline-none focus:ring-2 focus:ring-primary"
          dir="rtl"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => {
            if (draft !== content) onChange(draft);
          }}
        />
      </div>
    </div>
  );
}

function BlockView({ block }: { block: DocumentBlock }) {
  switch (block.type) {
    case "heading":
      return block.level === 2 ? (
        <h2 className="text-2xl font-semibold leading-10 tracking-tight">{block.text}</h2>
      ) : (
        <h3 className="text-xl font-semibold leading-9">{block.text}</h3>
      );
    case "paragraph":
      return <p className="text-base leading-8 text-foreground/95">{block.text}</p>;
    case "unordered_list":
      return (
        <ul className="list-disc space-y-2 pe-5 text-base leading-8">
          {block.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      );
    case "ordered_list":
      return (
        <ol className="list-decimal space-y-2 pe-5 text-base leading-8">
          {block.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      );
    case "cta":
      return (
        <div className="rounded-lg border border-primary/30 bg-primary/10 px-4 py-3">
          <p className="text-sm font-semibold text-foreground">{block.text}</p>
          {block.url ? (
            <a
              className="mt-1 block break-all text-sm text-primary underline"
              href={block.url}
              target="_blank"
              rel="noreferrer"
              dir="ltr"
            >
              {block.url}
            </a>
          ) : null}
        </div>
      );
    default:
      return null;
  }
}

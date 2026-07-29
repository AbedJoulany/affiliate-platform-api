"use client";

import { Badge } from "@/components/ui/primitives";
import type { ProductPipelineState } from "../lib/inventory";

export function ProductHealthBadges({
  state,
}: {
  state: ProductPipelineState;
}) {
  if (state.published) {
    return <Badge tone="success">منشور</Badge>;
  }

  return (
    <div className="flex max-w-40 flex-wrap gap-1">
      {state.queued ? <Badge tone="info">في القائمة</Badge> : null}
      {state.hasContent ? (
        <Badge tone="success">محتوى AI</Badge>
      ) : (
        <Badge tone="warning">ينقصه محتوى</Badge>
      )}
      {state.lowScore ? <Badge tone="error">نتيجة منخفضة</Badge> : null}
    </div>
  );
}

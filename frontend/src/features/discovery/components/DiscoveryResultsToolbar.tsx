"use client";

import { Button } from "@/components/ui/primitives";
import type { DiscoveryResponse } from "../types/api";

export function DiscoveryResultsToolbar({
  response,
  onPageChange,
}: {
  response: DiscoveryResponse | null;
  onPageChange: (page: number) => void;
}) {
  if (!response) return null;
  const page = response.page;
  const totalPages = Math.max(response.total_pages, 1);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground">
        {response.items.length.toLocaleString("ar")} من أصل {response.total.toLocaleString("ar")} نتيجة
        · الصفحة {page.toLocaleString("ar")} / {totalPages.toLocaleString("ar")}
      </p>
      <div className="flex items-center gap-2">
        {/* Extension: density toggle / grid view switch */}
        <Button
          variant="outline"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          السابق
        </Button>
        <Button
          variant="outline"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          التالي
        </Button>
      </div>
    </div>
  );
}

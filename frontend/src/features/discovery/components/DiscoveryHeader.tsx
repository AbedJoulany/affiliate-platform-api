"use client";

import { Button } from "@/components/ui/primitives";
import { PageHeader } from "@/components/layout/page";
import { formatDate } from "@/lib/utils";
import type { DiscoveryRunStatus } from "../types/api";
import { DiscoveryStats } from "./DiscoveryStats";

export function DiscoveryHeader({
  lastRunAt,
  lastRunStatus,
  canRun,
  running,
  onRun,
  totalDiscovered,
  pendingReview,
  importedCount,
}: {
  lastRunAt: string | null;
  lastRunStatus: DiscoveryRunStatus;
  canRun: boolean;
  running: boolean;
  onRun: () => void;
  totalDiscovered: number;
  pendingReview: number;
  importedCount: number;
}) {
  const description =
    lastRunAt != null
      ? `آخر تشغيل: ${formatDate(lastRunAt)}${lastRunStatus === "error" ? " · فشل" : ""}`
      : "مساحة إدخال المنتجات إلى مسار الأتمتة. شغّل الاكتشاف صراحةً عند الجاهزية.";

  return (
    <div className="space-y-3">
      <PageHeader
        title="اكتشاف المنتجات"
        description={description}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" disabled={!canRun} loading={running} onClick={onRun}>
              تشغيل الاكتشاف
            </Button>
          </div>
        }
      />
      <DiscoveryStats
        totalDiscovered={totalDiscovered}
        lastRunStatus={lastRunStatus}
        pendingReview={pendingReview}
        importedCount={importedCount}
      />
    </div>
  );
}

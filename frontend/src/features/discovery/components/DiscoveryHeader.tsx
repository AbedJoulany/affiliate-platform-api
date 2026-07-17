"use client";

import { Button } from "@/components/ui/primitives";
import { PageHeader } from "@/components/layout/page";
import { formatDate } from "@/lib/utils";
import type { DiscoveryRunStatus } from "../types/api";

export function DiscoveryHeader({
  lastRunAt,
  lastRunStatus,
  canRun,
  running,
  onRun,
}: {
  lastRunAt: string | null;
  lastRunStatus: DiscoveryRunStatus;
  canRun: boolean;
  running: boolean;
  onRun: () => void;
}) {
  const description =
    lastRunAt != null
      ? `آخر تشغيل: ${formatDate(lastRunAt)}${lastRunStatus === "error" ? " · فشل" : ""}`
      : "مساحة إدخال المنتجات إلى مسار الأتمتة. شغّل الاكتشاف صراحةً عند الجاهزية.";

  return (
    <PageHeader
      title="اكتشاف المنتجات"
      description={description}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {/* Extension: Discovery Profiles / Scheduled discovery */}
          <Button type="button" disabled={!canRun} loading={running} onClick={onRun}>
            تشغيل الاكتشاف
          </Button>
        </div>
      }
    />
  );
}

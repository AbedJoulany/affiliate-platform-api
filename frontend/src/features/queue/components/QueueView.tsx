"use client";

import { useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Button, Select } from "@/components/ui/primitives";
import { formatDate } from "@/lib/utils";
import { usePublishQueueItem, useQueue } from "../hooks/useQueue";
import { QUEUE_STATUSES, type QueueStatus } from "../types/api";

const statusLabels: Record<QueueStatus, string> = {
  draft: "مسودة",
  queued: "في الانتظار",
  scheduled: "مجدول",
  published: "منشور",
};

export function QueueView() {
  const [status, setStatus] = useState<QueueStatus | undefined>();
  const queue = useQueue(status);
  const publish = usePublishQueueItem();
  return (
    <PageContainer>
      <PageHeader title="قائمة النشر" description="أدر دورة حياة المحتوى ومواعيد النشر." actions={<Select className="w-44" aria-label="تصفية الحالة" value={status ?? ""} onChange={(event) => setStatus((event.target.value || undefined) as QueueStatus | undefined)}><option value="">كل الحالات</option>{QUEUE_STATUSES.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}</Select>} />
      {publish.isError && <p className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">{publish.error.message}</p>}
      {publish.isSuccess && <p className="mb-4 rounded-md bg-emerald-500/10 p-3 text-sm text-emerald-700" role="status">تم النشر بنجاح.</p>}
      {queue.isPending ? <LoadingState /> : queue.isError ? <ErrorState onRetry={() => void queue.refetch()} /> : queue.data.items.length === 0 ? <EmptyState title="قائمة النشر فارغة" description="أنشئ محتوى ثم أضفه إلى قائمة النشر." /> : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-muted/60 text-right text-muted-foreground"><tr><th className="p-3">المحتوى</th><th className="p-3">الموعد</th><th className="p-3">الحالة</th><th className="p-3">الإجراء</th></tr></thead>
            <tbody className="divide-y divide-border">
              {queue.data.items.map((item) => (
                <tr key={item.id}>
                  <td className="max-w-lg p-3"><p className="font-medium">{item.title || "بدون عنوان"}</p><p className="mt-1 line-clamp-1 text-muted-foreground">{item.content}</p></td>
                  <td className="p-3">{formatDate(item.scheduled_at ?? item.published_at)}</td>
                  <td className="p-3"><Badge tone={item.status === "published" ? "success" : item.status === "scheduled" ? "info" : "neutral"}>{statusLabels[item.status]}</Badge></td>
                  <td className="p-3"><Button variant="outline" disabled={item.status === "published"} loading={publish.isPending && publish.variables === item.id} onClick={() => { if (window.confirm("هل تريد نشر هذا المحتوى الآن؟")) publish.mutate(item.id); }}>نشر الآن</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageContainer>
  );
}

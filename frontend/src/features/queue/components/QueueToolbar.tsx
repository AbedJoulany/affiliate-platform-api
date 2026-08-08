"use client";

import type { ReactNode } from "react";
import { WorkspaceResultsToolbar } from "@/components/common/WorkspaceResultsToolbar";
import { Select } from "@/components/ui/primitives";
import type { Channel } from "@/features/channels/types/api";
import type {
  QueueStatus,
  QueueTableDensity,
  QueueWorkspaceSort,
} from "../types/api";

export function QueueToolbar({
  search,
  status,
  channel,
  sort,
  density,
  pageSize,
  resultCount,
  channels,
  refreshing,
  onSearchChange,
  onStatusChange,
  onChannelChange,
  onSortChange,
  onDensityChange,
  onPageSizeChange,
  onRefresh,
  actions,
}: {
  search: string;
  status: QueueStatus | "";
  channel: string;
  sort: QueueWorkspaceSort;
  density: QueueTableDensity;
  pageSize: number;
  resultCount: number;
  channels: Channel[];
  refreshing: boolean;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: QueueStatus | "") => void;
  onChannelChange: (value: string) => void;
  onSortChange: (value: QueueWorkspaceSort) => void;
  onDensityChange: (value: QueueTableDensity) => void;
  onPageSizeChange: (value: number) => void;
  onRefresh: () => void;
  /** Optional trailing slot (e.g. realtime status badge). */
  actions?: ReactNode;
}) {
  return (
    <WorkspaceResultsToolbar
      search={search}
      onSearchChange={onSearchChange}
      searchLabel="البحث في قائمة النشر"
      searchPlaceholder="العنوان أو المحتوى أو المنتج…"
      countLabel={`${resultCount.toLocaleString("ar")} منشور`}
      filters={
        <>
          <Select
            className="w-auto"
            aria-label="تصفية حسب حالة النشر"
            value={status}
            onChange={(event) => onStatusChange(event.target.value as QueueStatus | "")}
          >
            <option value="">كل الحالات</option>
            <option value="draft">مسودة</option>
            <option value="queued">في الانتظار</option>
            <option value="scheduled">مجدول</option>
            <option value="published">منشور</option>
          </Select>
          <Select
            className="w-auto"
            aria-label="تصفية حسب القناة"
            value={channel}
            onChange={(event) => onChannelChange(event.target.value)}
          >
            <option value="">كل القنوات</option>
            <option value="missing">بدون قناة</option>
            {channels.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title ?? item.username ?? item.telegram_channel_id}
              </option>
            ))}
          </Select>
        </>
      }
      sort={{
        value: sort,
        label: "ترتيب عمليات النشر",
        options: [
          { value: "newest", label: "الأحدث" },
          { value: "oldest", label: "الأقدم" },
          { value: "schedule_asc", label: "الموعد الأقرب" },
          { value: "schedule_desc", label: "الموعد الأبعد" },
          { value: "status", label: "الحالة" },
        ],
        onChange: onSortChange,
      }}
      density={{
        value: density,
        label: "كثافة الجدول",
        options: [
          { value: "comfortable", label: "مريح" },
          { value: "compact", label: "مضغوط" },
        ],
        onChange: onDensityChange,
      }}
      pageSize={{ value: pageSize, options: [10, 25, 50, 100], onChange: onPageSizeChange }}
      refreshing={refreshing}
      onRefresh={onRefresh}
      actions={actions}
    />
  );
}

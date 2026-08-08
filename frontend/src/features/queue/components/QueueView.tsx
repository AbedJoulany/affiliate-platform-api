"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/states";
import { ToastOverlay } from "@/components/common/ToastOverlay";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Button } from "@/components/ui/primitives";
import type { ApiError } from "@/services/api-client";
import { useChannels } from "@/features/channels/hooks/useChannels";
import { useProducts } from "@/features/products/hooks/useProducts";
import { getQueueOperationalStats } from "../lib/operations";
import {
  useDeleteQueueItem,
  useQueue,
  useQueueAttemptSummaryEnrichment,
  useQueuePublishingOperations,
  useQueueWorkspaceState,
  useUpdateQueueItem,
} from "../hooks/useQueue";
import { useQueueRealtimeInvalidation } from "../hooks/useQueueRealtimeInvalidation";
import { QueueRealtimePollingContext } from "../hooks/QueueRealtimePollingContext";
import type { QueueEventStreamStatus } from "../hooks/useQueueEventStream";
import type { QueueItem, QueueStatus } from "../types/api";
import { QueueDetailsDrawer } from "./QueueDetailsDrawer";
import { QueueOperationalStats } from "./QueueOperationalStats";
import { QueueRealtimeStatusBadge } from "./QueueRealtimeStatusBadge";
import { QueueSchedulingDialog } from "./QueueSchedulingDialog";
import { QueueSelectionBar } from "./QueueSelectionBar";
import { QueueTable } from "./QueueTable";
import { QueueToolbar } from "./QueueToolbar";

type SchedulingState = {
  itemIds: string[];
  channelId: string;
  scheduledAt: string;
};

type ToastState = {
  message: string;
  tone: "success" | "error";
} | null;

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (
    error &&
    typeof error === "object" &&
    "message" in error &&
    typeof (error as ApiError).message === "string" &&
    (error as ApiError).message.length > 0
  ) {
    return (error as ApiError).message;
  }
  return fallback;
}

export function QueueView() {
  // Single workspace-scoped SSE → query invalidation (not in child components).
  const realtime = useQueueRealtimeInvalidation();

  return (
    <QueueRealtimePollingContext.Provider value={realtime.pollingEnabled}>
      <QueueViewBody realtimeStatus={realtime.status} />
    </QueueRealtimePollingContext.Provider>
  );
}

function QueueViewBody({
  realtimeStatus,
}: {
  realtimeStatus: QueueEventStreamStatus;
}) {
  const router = useRouter();
  const queue = useQueue(undefined, 200);
  const channels = useChannels();
  const products = useProducts({ limit: 200, skip: 0 });
  const updateQueue = useUpdateQueueItem();
  const deleteQueue = useDeleteQueueItem();
  const publishing = useQueuePublishingOperations();
  const listItems = useMemo(
    () => queue.data?.items ?? [],
    [queue.data?.items],
  );
  const { enrichedItems, enriching } = useQueueAttemptSummaryEnrichment(listItems);
  const workspace = useQueueWorkspaceState(enrichedItems);

  const [activePostId, setActivePostId] = useState<string | null>(null);
  const [schedulingDialog, setSchedulingDialog] = useState<SchedulingState | null>(
    null,
  );
  const [deleteTargets, setDeleteTargets] = useState<QueueItem[]>([]);
  const [toast, setToast] = useState<ToastState>(null);

  useEffect(() => {
    publishing.syncFailuresFromBackend(enrichedItems);
  }, [enrichedItems, publishing.syncFailuresFromBackend]);

  const productsById = useMemo(
    () => new Map((products.data?.items ?? []).map((product) => [product.id, product])),
    [products.data?.items],
  );
  const channelsById = useMemo(
    () => new Map((channels.data?.items ?? []).map((channel) => [channel.id, channel])),
    [channels.data?.items],
  );
  const stats = useMemo(
    () =>
      getQueueOperationalStats(
        enrichedItems,
        publishing.publishingIdSet,
        publishing.failures,
      ),
    [enrichedItems, publishing.publishingIdSet, publishing.failures],
  );

  const activePost = useMemo(
    () =>
      activePostId
        ? enrichedItems.find((item) => item.id === activePostId) ?? null
        : null,
    [activePostId, enrichedItems],
  );

  // Close inspector when the authoritative list no longer contains the item
  // (e.g. queue.deleted → invalidate → refetch), without a separate client store.
  useEffect(() => {
    if (activePostId == null || queue.isPending) return;
    if (!listItems.some((item) => item.id === activePostId)) {
      setActivePostId(null);
    }
  }, [activePostId, listItems, queue.isPending]);

  const activeProduct =
    activePost?.product_id ? productsById.get(activePost.product_id) ?? null : null;
  const activeChannel =
    activePost?.channel_id ? channelsById.get(activePost.channel_id) ?? null : null;
  const busy = updateQueue.isPending || deleteQueue.isPending;

  const openSchedule = (selected: QueueItem[]) => {
    if (selected.length === 0) return;
    const first = selected[0];
    setSchedulingDialog({
      itemIds: selected.map((item) => item.id),
      channelId: first.channel_id ?? "",
      scheduledAt: first.scheduled_at ? toDateTimeLocal(new Date(first.scheduled_at)) : "",
    });
  };

  const publishItems = async (selected: QueueItem[]) => {
    if (selected.length === 0) return;
    if (selected.some((item) => !item.channel_id)) {
      openSchedule(selected);
      setToast({
        tone: "error",
        message: "عيّن قناة مستهدفة قبل النشر.",
      });
      return;
    }
    const result = await publishing.publishItems(selected.map((item) => item.id));
    if (result.conflicts > 0 && result.published === 0 && result.failed === 0) {
      setToast({
        tone: "error",
        message: result.conflictMessage ?? "تعذر النشر بسبب تعارض.",
      });
    } else if (result.failed > 0 || result.conflicts > 0) {
      const parts = [
        result.published > 0
          ? `نُشر ${result.published.toLocaleString("ar")}`
          : null,
        result.failed > 0
          ? `فشل ${result.failed.toLocaleString("ar")}${
              result.failureMessage ? `: ${result.failureMessage}` : ""
            }`
          : null,
        result.conflicts > 0
          ? `تعارض ${result.conflicts.toLocaleString("ar")}${
              result.conflictMessage ? `: ${result.conflictMessage}` : ""
            }`
          : null,
      ].filter(Boolean);
      setToast({ tone: "error", message: parts.join(" · ") });
    } else {
      setToast({
        tone: "success",
        message: `تم نشر ${result.published.toLocaleString("ar")} منشور بنجاح.`,
      });
    }
    workspace.clearSelection();
  };

  const saveSchedule = async () => {
    if (!schedulingDialog?.channelId || !schedulingDialog.scheduledAt) return;
    try {
      const scheduledAt = new Date(schedulingDialog.scheduledAt).toISOString();
      for (const id of schedulingDialog.itemIds) {
        await updateQueue.mutateAsync({
          id,
          input: {
            channel_id: schedulingDialog.channelId,
            status: "scheduled",
            scheduled_at: scheduledAt,
          },
        });
      }
      setSchedulingDialog(null);
      workspace.clearSelection();
      setToast({ tone: "success", message: "تم تحديث موعد النشر." });
    } catch (error) {
      setToast({
        tone: "error",
        message: getApiErrorMessage(error, "تعذر حفظ الجدولة."),
      });
    }
  };

  const publishFromDialog = async () => {
    if (!schedulingDialog?.channelId) return;
    try {
      const selected = enrichedItems.filter((item) =>
        schedulingDialog.itemIds.includes(item.id),
      );
      for (const item of selected) {
        await updateQueue.mutateAsync({
          id: item.id,
          input: {
            channel_id: schedulingDialog.channelId,
            status: "queued",
          },
        });
      }
      setSchedulingDialog(null);
      await publishItems(
        selected.map((item) => ({
          ...item,
          channel_id: schedulingDialog.channelId,
          status: "queued" as const,
        })),
      );
    } catch (error) {
      setToast({
        tone: "error",
        message: getApiErrorMessage(error, "تعذر تجهيز النشر."),
      });
    }
  };

  const changeStatus = async (status: Extract<QueueStatus, "draft" | "queued">) => {
    try {
      for (const item of workspace.selectedItems) {
        await updateQueue.mutateAsync({ id: item.id, input: { status } });
      }
      workspace.clearSelection();
      setToast({ tone: "success", message: "تم تحديث حالة المنشورات." });
    } catch (error) {
      setToast({
        tone: "error",
        message: getApiErrorMessage(error, "تعذر تحديث الحالة."),
      });
    }
  };

  const confirmDelete = async () => {
    try {
      for (const item of deleteTargets) {
        await deleteQueue.mutateAsync(item.id);
      }
      if (deleteTargets.some((item) => item.id === activePostId)) {
        setActivePostId(null);
      }
      setToast({
        tone: "success",
        message: `تم حذف ${deleteTargets.length.toLocaleString("ar")} منشور.`,
      });
      setDeleteTargets([]);
      workspace.clearSelection();
    } catch (error) {
      setToast({
        tone: "error",
        message: getApiErrorMessage(error, "تعذر حذف المنشورات."),
      });
    }
  };

  const openAi = (item: QueueItem) => {
    if (item.product_id) {
      router.push(`/ai?product=${encodeURIComponent(item.product_id)}`);
      return;
    }
    if (item.button_url) {
      router.push(`/ai?url=${encodeURIComponent(item.button_url)}`);
    }
  };

  const noItems = !queue.isPending && !queue.isError && listItems.length === 0;
  const filteredEmpty =
    !queue.isPending &&
    !queue.isError &&
    listItems.length > 0 &&
    workspace.filteredItems.length === 0;

  return (
    <PageContainer wide>
      <PageHeader
        title="مركز عمليات النشر"
        description="راجع الجاهزية، عيّن القنوات، وجدول وراقب عمليات النشر."
        actions={
          <Link href="/ai">
            <Button variant="outline">العودة إلى AI Studio</Button>
          </Link>
        }
      />

      <div className="space-y-4">
        <QueueOperationalStats stats={stats} />
        <QueueToolbar
          search={workspace.search}
          status={workspace.statusFilter}
          channel={workspace.channelFilter}
          sort={workspace.sort}
          density={workspace.density}
          pageSize={workspace.pageSize}
          resultCount={workspace.filteredItems.length}
          channels={channels.data?.items ?? []}
          refreshing={
            queue.isFetching ||
            channels.isFetching ||
            products.isFetching ||
            enriching
          }
          onSearchChange={workspace.setSearch}
          onStatusChange={workspace.setStatusFilter}
          onChannelChange={workspace.setChannelFilter}
          onSortChange={workspace.setSort}
          onDensityChange={workspace.setDensity}
          onPageSizeChange={workspace.setPageSize}
          onRefresh={() => {
            void queue.refetch();
            void channels.refetch();
            void products.refetch();
          }}
          actions={<QueueRealtimeStatusBadge status={realtimeStatus} />}
        />

        {queue.isPending ? (
          <LoadingState rows={8} />
        ) : queue.isError ? (
          <ErrorState
            message="تعذر تحميل عمليات النشر."
            onRetry={() => void queue.refetch()}
          />
        ) : noItems ? (
          <EmptyState
            title="لا توجد عمليات نشر"
            description="أنشئ المحتوى في AI Studio ثم أضفه إلى قائمة النشر لبدء التشغيل."
            action={
              <Link href="/ai">
                <Button>فتح AI Studio</Button>
              </Link>
            }
          />
        ) : filteredEmpty ? (
          <EmptyState
            title="لا توجد نتائج مطابقة"
            description="غيّر البحث أو الحالة أو القناة لعرض عمليات أخرى."
            action={
              <Button
                variant="outline"
                onClick={() => {
                  workspace.setSearch("");
                  workspace.setStatusFilter("");
                  workspace.setChannelFilter("");
                }}
              >
                مسح عوامل التصفية
              </Button>
            }
          />
        ) : (
          <>
            <QueueTable
              items={workspace.pagedItems}
              selectedIds={workspace.selectedQueueItemIds}
              allSelected={workspace.allPageSelected}
              density={workspace.density}
              productsById={productsById}
              channelsById={channelsById}
              publishingIds={publishing.publishingIdSet}
              failures={publishing.failures}
              onToggle={workspace.toggle}
              onToggleAll={workspace.toggleAll}
              onView={(item) => setActivePostId(item.id)}
              onOpenProduct={(productId) => router.push(`/products/${productId}`)}
              onSchedule={(item) => openSchedule([item])}
              onPublish={(item) => void publishItems([item])}
              onOpenAi={openAi}
              onDelete={(item) => setDeleteTargets([item])}
            />
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                صفحة {(workspace.page + 1).toLocaleString("ar")} من{" "}
                {Math.max(
                  1,
                  Math.ceil(workspace.filteredItems.length / workspace.pageSize),
                ).toLocaleString("ar")}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  disabled={workspace.page === 0}
                  onClick={() => workspace.setPage(workspace.page - 1)}
                >
                  السابق
                </Button>
                <Button
                  variant="outline"
                  disabled={
                    (workspace.page + 1) * workspace.pageSize >=
                    workspace.filteredItems.length
                  }
                  onClick={() => workspace.setPage(workspace.page + 1)}
                >
                  التالي
                </Button>
              </div>
            </div>
          </>
        )}

        <QueueSelectionBar
          count={workspace.selectedQueueItemIds.length}
          busy={busy || publishing.publishingIds.length > 0}
          onClear={workspace.clearSelection}
          onPublish={() => void publishItems(workspace.selectedItems)}
          onReschedule={() => openSchedule(workspace.selectedItems)}
          onDelete={() => setDeleteTargets(workspace.selectedItems)}
          onChangeStatus={(status) => void changeStatus(status)}
        />
      </div>

      <QueueDetailsDrawer
        item={activePost}
        product={activeProduct}
        channel={activeChannel}
        publishing={Boolean(activePost && publishing.publishingIdSet.has(activePost.id))}
        clientFailure={activePost ? publishing.failures[activePost.id] : undefined}
        open={activePost != null}
        onClose={() => setActivePostId(null)}
        onPublish={(item) => void publishItems([item])}
        onSchedule={(item) => openSchedule([item])}
        onOpenAi={openAi}
      />

      <QueueSchedulingDialog
        open={schedulingDialog != null}
        itemCount={schedulingDialog?.itemIds.length ?? 0}
        channelId={schedulingDialog?.channelId ?? ""}
        scheduledAt={schedulingDialog?.scheduledAt ?? ""}
        channels={channels.data?.items ?? []}
        busy={updateQueue.isPending || publishing.publishingIds.length > 0}
        onChannelChange={(channelId) =>
          setSchedulingDialog((previous) =>
            previous ? { ...previous, channelId } : previous,
          )
        }
        onScheduledAtChange={(scheduledAt) =>
          setSchedulingDialog((previous) =>
            previous ? { ...previous, scheduledAt } : previous,
          )
        }
        onPublishNow={() => void publishFromDialog()}
        onApply={() => void saveSchedule()}
        onClose={() => setSchedulingDialog(null)}
      />

      <ConfirmDialog
        open={deleteTargets.length > 0}
        title={`حذف ${deleteTargets.length.toLocaleString("ar")} منشور؟`}
        message="سيُحذف من قائمة النشر دون حذف المنتج أو محتوى AI الأصلي."
        confirmLabel="حذف"
        destructive
        busy={deleteQueue.isPending}
        onCancel={() => setDeleteTargets([])}
        onConfirm={() => void confirmDelete()}
      />

      <ToastOverlay
        message={toast?.message ?? null}
        tone={toast?.tone}
        onDismiss={() => setToast(null)}
      />
    </PageContainer>
  );
}

function toDateTimeLocal(date: Date): string {
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

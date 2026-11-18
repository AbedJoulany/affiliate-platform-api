"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  NoActiveWorkspaceState,
} from "@/components/common/states";
import { ToastOverlay } from "@/components/common/ToastOverlay";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Button, Card } from "@/components/ui/primitives";
import { getApiErrorMessage } from "@/services/api-client";
import {
  useChannels,
  useFacebookPages,
} from "@/features/channels/hooks/useChannels";
import type { FacebookPage } from "@/features/channels/types/api";
import { useProducts } from "@/features/products/hooks/useProducts";
import { useActiveWorkspaceId } from "@/lib/workspace";
import { getQueueOperationalStats } from "../lib/operations";
import { nextStatusAfterFailedRetry } from "../lib/retry";
import {
  useDeleteQueueItem,
  useQueue,
  useQueueItem,
  useQueueAttemptSummaryEnrichment,
  useQueuePublishingOperations,
  useQueueWorkspaceState,
  useUpdateQueueItem,
} from "../hooks/useQueue";
import type { PublishOptions } from "../hooks/useQueue";
import { useQueueRealtimeInvalidation } from "../hooks/useQueueRealtimeInvalidation";
import { QueueRealtimePollingContext } from "../hooks/QueueRealtimePollingContext";
import type { QueueEventStreamStatus } from "../hooks/useQueueEventStream";
import type { QueueItem, QueueStatus } from "../types/api";
import { QueueDetailsDrawer } from "./QueueDetailsDrawer";
import { QueueOperationalStats } from "./QueueOperationalStats";
import { QueueRealtimeStatusBadge } from "./QueueRealtimeStatusBadge";
import {
  QueueSchedulingDialog,
  type QueuePublishNowSubmitValues,
  type QueueScheduleSubmitValues,
} from "./QueueSchedulingDialog";
import { QueueSelectionBar } from "./QueueSelectionBar";
import { QueueTable } from "./QueueTable";
import { QueueToolbar } from "./QueueToolbar";
import {
  destinationSelectionFromQueue,
  destinationSelectionIsReady,
  destinationSelectionPatch,
  type DestinationSelection,
} from "./PublishingDestinationSelector";

type SchedulingState = {
  itemIds: string[];
  destination: DestinationSelection;
  scheduledAt: string;
  preserveDestinations: boolean;
};

type ToastState = {
  message: string;
  tone: "success" | "error";
} | null;

const QUEUE_ITEM_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValidQueueItemId(value: string | null): value is string {
  return value != null && QUEUE_ITEM_ID_RE.test(value);
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
  const searchParams = useSearchParams();
  const workspaceId = useActiveWorkspaceId();
  const queue = useQueue(undefined, 200);
  const channels = useChannels();
  const facebookPages = useFacebookPages();
  const products = useProducts({ limit: 200, skip: 0 });
  const updateQueue = useUpdateQueueItem();
  const deleteQueue = useDeleteQueueItem();
  const publishing = useQueuePublishingOperations();
  const listItems = useMemo(() => queue.data?.items ?? [], [queue.data?.items]);
  const { enrichedItems, enriching } =
    useQueueAttemptSummaryEnrichment(listItems);
  const workspace = useQueueWorkspaceState(enrichedItems);

  const requestedItemId = searchParams.get("item");
  const validRequestedItemId = isValidQueueItemId(requestedItemId)
    ? requestedItemId
    : null;
  const requestedItemInList = Boolean(
    validRequestedItemId &&
    listItems.some((item) => item.id === validRequestedItemId),
  );
  const deepLinkedItem = useQueueItem(
    validRequestedItemId,
    queue.isFetched && !queue.isError && !requestedItemInList,
  );

  const [activePostId, setActivePostId] = useState<string | null>(null);
  const [selectionWorkspaceId, setSelectionWorkspaceId] = useState<
    string | null
  >(null);
  const [schedulingDialog, setSchedulingDialog] =
    useState<SchedulingState | null>(null);
  const [deleteTargets, setDeleteTargets] = useState<QueueItem[]>([]);
  const [toast, setToast] = useState<ToastState>(null);

  useEffect(() => {
    publishing.syncFailuresFromBackend(enrichedItems);
  }, [enrichedItems, publishing.syncFailuresFromBackend]);

  const productsById = useMemo(
    () =>
      new Map(
        (products.data?.items ?? []).map((product) => [product.id, product]),
      ),
    [products.data?.items],
  );
  const channelsById = useMemo(
    () =>
      new Map(
        (channels.data?.items ?? []).map((channel) => [channel.id, channel]),
      ),
    [channels.data?.items],
  );
  const facebookPagesById = useMemo(
    () =>
      new Map(
        (facebookPages.data?.items ?? []).map((page: FacebookPage) => [
          page.id,
          page,
        ]),
      ),
    [facebookPages.data?.items],
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
      activePostId && selectionWorkspaceId === workspaceId
        ? (enrichedItems.find((item) => item.id === activePostId) ??
          (deepLinkedItem.data?.id === activePostId
            ? deepLinkedItem.data
            : null))
        : null,
    [
      activePostId,
      deepLinkedItem.data,
      enrichedItems,
      selectionWorkspaceId,
      workspaceId,
    ],
  );

  const replaceItemParam = (itemId: string | null) => {
    const nextParams = new URLSearchParams(searchParams.toString());
    if (itemId) nextParams.set("item", itemId);
    else nextParams.delete("item");
    const query = nextParams.toString();
    router.replace(query ? `/queue?${query}` : "/queue", { scroll: false });
  };

  const selectItem = (itemId: string) => {
    setActivePostId(itemId);
    setSelectionWorkspaceId(workspaceId);
    replaceItemParam(itemId);
  };

  const clearSelectedItem = () => {
    setActivePostId(null);
    setSelectionWorkspaceId(null);
    if (searchParams.has("item")) replaceItemParam(null);
  };

  useEffect(() => {
    setActivePostId(null);
    setSelectionWorkspaceId(null);
  }, [workspaceId]);

  // Close inspector when the authoritative list no longer contains the item
  // (e.g. queue.deleted → invalidate → refetch), without a separate client store.
  useEffect(() => {
    if (activePostId == null || queue.isPending) return;
    if (
      !listItems.some((item) => item.id === activePostId) &&
      deepLinkedItem.data?.id !== activePostId
    ) {
      setActivePostId(null);
    }
  }, [activePostId, deepLinkedItem.data?.id, listItems, queue.isPending]);

  useEffect(() => {
    if (!requestedItemId) {
      setActivePostId(null);
      setSelectionWorkspaceId(null);
      return;
    }
    if (!validRequestedItemId || queue.isPending) {
      setActivePostId(null);
      setSelectionWorkspaceId(null);
      return;
    }
    if (
      requestedItemInList ||
      deepLinkedItem.data?.id === validRequestedItemId
    ) {
      setActivePostId(validRequestedItemId);
      setSelectionWorkspaceId(workspaceId);
    }
  }, [
    deepLinkedItem.data?.id,
    queue.isPending,
    requestedItemInList,
    requestedItemId,
    validRequestedItemId,
    workspaceId,
  ]);

  const activeProduct = activePost?.product_id
    ? (productsById.get(activePost.product_id) ?? null)
    : null;
  const activeChannel = activePost?.channel_id
    ? (channelsById.get(activePost.channel_id) ?? null)
    : null;
  const busy = updateQueue.isPending || deleteQueue.isPending;

  const openSchedule = (selected: QueueItem[]) => {
    if (selected.length === 0) return;
    const first = selected[0];
    const destinationsReady = selected.every((item) =>
      destinationSelectionIsReady(
        destinationSelectionFromQueue(item),
        channels.data?.items ?? [],
        facebookPages.data?.items ?? [],
      ),
    );
    if (selected.length > 1 && !destinationsReady) {
      setToast({
        tone: "error",
        message:
          "أكمل وجهة كل منشور قبل الجدولة الجماعية؛ لن يتم تعيين وجهة تلقائيًا.",
      });
      return;
    }
    setSchedulingDialog({
      itemIds: selected.map((item) => item.id),
      destination: destinationSelectionFromQueue(first),
      scheduledAt: first.scheduled_at
        ? toDateTimeLocal(new Date(first.scheduled_at))
        : "",
      preserveDestinations: selected.length > 1,
    });
  };

  const publishItems = async (
    selected: QueueItem[],
    options: PublishOptions = {},
  ) => {
    if (selected.length === 0) return;
    if (
      selected.some(
        (item) =>
          !destinationSelectionIsReady(
            destinationSelectionFromQueue(item),
            channels.data?.items ?? [],
            facebookPages.data?.items ?? [],
          ),
      )
    ) {
      openSchedule(selected);
      setToast({
        tone: "error",
        message: "عيّن قناة مستهدفة قبل النشر.",
      });
      return;
    }
    const result = await publishing.publishItems(
      selected.map((item) => item.id),
      options,
    );
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

  const saveSchedule = async (values: QueueScheduleSubmitValues) => {
    if (!schedulingDialog) return;
    try {
      const scheduledAt = new Date(values.scheduledAt).toISOString();
      for (const id of schedulingDialog.itemIds) {
        await updateQueue.mutateAsync({
          id,
          input: {
            ...(schedulingDialog.preserveDestinations
              ? {}
              : destinationSelectionPatch(values.destination)),
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

  const publishFromDialog = async (values: QueuePublishNowSubmitValues) => {
    if (!schedulingDialog) return;
    try {
      const selected = enrichedItems.filter((item) =>
        schedulingDialog.itemIds.includes(item.id),
      );
      for (const item of selected) {
        await updateQueue.mutateAsync({
          id: item.id,
          input: {
            ...(schedulingDialog.preserveDestinations
              ? {}
              : destinationSelectionPatch(values.destination)),
            status: "queued",
          },
        });
      }
      setSchedulingDialog(null);
      await publishItems(
        selected.map((item) => ({
          ...item,
          ...(schedulingDialog.preserveDestinations
            ? {}
            : destinationSelectionPatch(values.destination)),
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

  const retryFailedItem = async (
    item: QueueItem,
    options: PublishOptions = {},
  ) => {
    try {
      if (options.confirmAmbiguous) {
        await publishItems([item], options);
        return;
      }
      const next = nextStatusAfterFailedRetry(item);
      const updated = await updateQueue.mutateAsync({
        id: item.id,
        input: next,
      });
      if (updated.status === "queued") {
        await publishItems([{ ...item, ...updated }]);
        return;
      }
      setToast({ tone: "success", message: "تمت إعادة جدولة المنشور الفاشل." });
    } catch (error) {
      setToast({
        tone: "error",
        message: getApiErrorMessage(error, "تعذر إعادة محاولة النشر."),
      });
    }
  };

  const changeStatus = async (
    status: Extract<QueueStatus, "draft" | "queued">,
  ) => {
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
        clearSelectedItem();
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

  if (!workspaceId) {
    return (
      <PageContainer wide>
        <PageHeader
          title="مركز عمليات النشر"
          description="راجع الجاهزية، عيّن القنوات، وجدول وراقب عمليات النشر."
        />
        <NoActiveWorkspaceState />
      </PageContainer>
    );
  }

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
          realtimeStatus={realtimeStatus}
          actions={<QueueRealtimeStatusBadge status={realtimeStatus} />}
        />

        {queue.isPending ? (
          <LoadingState rows={8} />
        ) : queue.isError ? (
          <ErrorState
            message={getApiErrorMessage(
              queue.error,
              "تعذر تحميل عمليات النشر.",
            )}
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
              facebookPagesById={facebookPagesById}
              publishingIds={publishing.publishingIdSet}
              failures={publishing.failures}
              onToggle={workspace.toggle}
              onToggleAll={workspace.toggleAll}
              onView={(item) => selectItem(item.id)}
              onOpenProduct={(productId) =>
                router.push(`/products/${productId}`)
              }
              onSchedule={(item) => openSchedule([item])}
              onPublish={(item) => void publishItems([item])}
              onRetry={(item) => void retryFailedItem(item)}
              onOpenAi={openAi}
              onDelete={(item) => setDeleteTargets([item])}
            />
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                صفحة {(workspace.page + 1).toLocaleString("ar")} من{" "}
                {Math.max(
                  1,
                  Math.ceil(
                    workspace.filteredItems.length / workspace.pageSize,
                  ),
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

      {requestedItemId && !validRequestedItemId ? (
        <QueueDeepLinkNotice
          message="رابط عملية النشر غير صالح."
          onClear={clearSelectedItem}
        />
      ) : validRequestedItemId &&
        queue.isFetched &&
        !queue.isError &&
        !requestedItemInList &&
        deepLinkedItem.isPending ? (
        <QueueDeepLinkNotice message="جاري فتح عملية النشر المطلوبة…" loading />
      ) : validRequestedItemId &&
        queue.isFetched &&
        !queue.isError &&
        !requestedItemInList &&
        deepLinkedItem.isError ? (
        <QueueDeepLinkNotice
          message="تعذر فتح عملية النشر المطلوبة أو لم تعد متاحة."
          onClear={clearSelectedItem}
        />
      ) : null}

      <QueueDetailsDrawer
        item={activePost}
        product={activeProduct}
        channel={activeChannel}
        facebookPage={
          activePost?.facebook_page_id
            ? (facebookPagesById.get(activePost.facebook_page_id) ?? null)
            : null
        }
        publishing={Boolean(
          activePost && publishing.publishingIdSet.has(activePost.id),
        )}
        clientFailure={
          activePost ? publishing.failures[activePost.id] : undefined
        }
        open={activePost != null}
        onClose={clearSelectedItem}
        onPublish={(item) => void publishItems([item])}
        onRetry={(item, options) => void retryFailedItem(item, options)}
        onSchedule={(item) => openSchedule([item])}
        onOpenAi={openAi}
      />

      <QueueSchedulingDialog
        open={schedulingDialog != null}
        itemCount={schedulingDialog?.itemIds.length ?? 0}
        defaultValues={{
          destination: schedulingDialog?.destination ?? {
            provider: "telegram",
            channelId: null,
            facebookPageId: null,
          },
          scheduledAt: schedulingDialog?.scheduledAt ?? "",
        }}
        channels={channels.data?.items ?? []}
        facebookPages={facebookPages.data?.items ?? []}
        preserveDestinations={schedulingDialog?.preserveDestinations ?? false}
        busy={updateQueue.isPending || publishing.publishingIds.length > 0}
        onSchedule={(values) => void saveSchedule(values)}
        onPublishNow={(values) => void publishFromDialog(values)}
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

function QueueDeepLinkNotice({
  message,
  loading = false,
  onClear,
}: {
  message: string;
  loading?: boolean;
  onClear?: () => void;
}) {
  return (
    <Card
      className="mt-4 flex flex-wrap items-center justify-between gap-3"
      role={loading ? "status" : "alert"}
      aria-live="polite"
    >
      <p className="text-sm text-muted-foreground">{message}</p>
      {onClear ? (
        <Button variant="outline" onClick={onClear}>
          عرض قائمة النشر
        </Button>
      ) : null}
    </Card>
  );
}

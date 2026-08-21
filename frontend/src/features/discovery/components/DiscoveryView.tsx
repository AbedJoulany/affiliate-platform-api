"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorState, LoadingState } from "@/components/common/states";
import { PageContainer } from "@/components/layout/page";
import { useCategories } from "@/features/categories/hooks/useCategories";
import { useCurrentUser } from "@/features/auth/hooks/useAuth";
import { generateContent } from "@/features/ai/api/ai.api";
import { createQueueItem } from "@/features/queue/api/queue.api";
import { getApiErrorMessage } from "@/services/api-client";
import { exportDiscoveryProductsCsv } from "../lib/export";
import { DEFAULT_VISIBLE_COLUMNS, normalizeUiPrefs } from "../lib/ui-prefs";
import {
  useDiscoveryQuery,
  useDiscoverySelection,
  useDiscoverySession,
  useImportProduct,
  useImportProductsBatch,
} from "../hooks/useDiscovery";
import type { DiscoveryMode, DiscoveryParams, DiscoveryProduct, DiscoveryTableColumn } from "../types/api";
import { validateDiscoveryDraft } from "./DiscoveryFilterPanel";
import { DiscoveryAdvancedFiltersDrawer } from "./DiscoveryAdvancedFiltersDrawer";
import { DiscoveryEmptyState } from "./DiscoveryEmptyState";
import { DiscoveryFilterBar } from "./DiscoveryFilterBar";
import { DiscoveryHeader } from "./DiscoveryHeader";
import { DiscoveryIntentTabs } from "./DiscoveryIntentTabs";
import { DiscoveryProductInspector } from "./DiscoveryProductInspector";
import { DiscoveryResultsTable } from "./DiscoveryResultsTable";
import { DiscoveryResultsToolbar } from "./DiscoveryResultsToolbar";
import { DiscoverySelectionBar } from "./DiscoverySelectionBar";

export function DiscoveryView() {
  const router = useRouter();
  const currentUser = useCurrentUser();
  const categories = useCategories();
  const {
    session,
    hydrated,
    updateDraft,
    updateUiPrefs,
    resetDraftFilters,
    markRunning,
    markSuccess,
    markError,
    trackImported,
  } = useDiscoverySession();

  const [runToken, setRunToken] = useState(0);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [inspectorId, setInspectorId] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const draft = session.draftParams;
  const committed = session.committedParams;
  const uiPrefs = normalizeUiPrefs(session.uiPrefs);
  const shouldFetch = runToken > 0 && committed != null;
  const discovery = useDiscoveryQuery(committed, shouldFetch);
  const singleImport = useImportProduct();
  const batchImport = useImportProductsBatch();

  const canImport = currentUser.data?.role === "admin";
  const draftError = validateDiscoveryDraft(draft);

  useEffect(() => {
    if (!discovery.isFetching && runToken > 0 && committed) {
      if (discovery.isSuccess && discovery.data) {
        markSuccess(committed, discovery.data);
      } else if (discovery.isError) {
        markError(getApiErrorMessage(discovery.error, "تعذر تشغيل الاكتشاف."));
      }
    }
  }, [
    discovery.isFetching,
    discovery.isSuccess,
    discovery.isError,
    discovery.data,
    discovery.error,
    runToken,
    committed,
    markSuccess,
    markError,
  ]);

  const items = useMemo(() => {
    if (discovery.isSuccess && discovery.data) return discovery.data.items;
    return session.lastResponse?.items ?? [];
  }, [discovery.isSuccess, discovery.data, session.lastResponse]);

  const filteredItems = useMemo(() => {
    const q = uiPrefs.resultSearch.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => item.title.toLowerCase().includes(q));
  }, [items, uiPrefs.resultSearch]);

  const response = discovery.data ?? session.lastResponse;
  const importedIds = useMemo(() => new Set(session.importedIds), [session.importedIds]);
  const pendingReview = items.filter((item) => !importedIds.has(item.aliexpress_product_id)).length;
  const selection = useDiscoverySelection(filteredItems);
  const { clear: clearSelection } = selection;
  const inspectorProduct = items.find((item) => item.aliexpress_product_id === inspectorId) ?? null;

  const runDiscovery = useCallback(
    (params: DiscoveryParams = draft) => {
      const error = validateDiscoveryDraft(params);
      if (error) {
        setActionError(error);
        return;
      }
      setActionError(null);
      setActionMessage(null);
      const next = { ...params, page: params.page ?? 1, page_size: params.page_size ?? 20 };
      markRunning(next);
      setRunToken((value) => value + 1);
      clearSelection();
    },
    [draft, markRunning, clearSelection],
  );

  const onPageChange = (page: number) => {
    if (!committed) return;
    runDiscovery({ ...committed, page });
  };

  const handleImportOne = async (product: DiscoveryProduct) => {
    if (!canImport) return;
    setActionError(null);
    try {
      await singleImport.mutateAsync(product.aliexpress_product_id);
      trackImported([product.aliexpress_product_id]);
      setActionMessage(`تم استيراد: ${product.title}`);
    } catch (error) {
      setActionError(getApiErrorMessage(error, "تعذر الاستيراد."));
    }
  };

  const handleImportSelected = async () => {
    if (!canImport || selection.selectedProducts.length === 0) return;
    setBatchBusy(true);
    setActionError(null);
    try {
      const ids = selection.selectedProducts.map((item) => item.aliexpress_product_id);
      const result = await batchImport.mutateAsync(ids);
      trackImported(ids);
      setActionMessage(
        `استيراد جماعي: ${result.imported} جديد · ${result.updated} محدّث · ${result.failed} فشل`,
      );
      selection.clear();
    } catch (error) {
      setActionError(getApiErrorMessage(error, "تعذر الاستيراد الجماعي."));
    } finally {
      setBatchBusy(false);
    }
  };

  const queueDraftFromProduct = async (product: DiscoveryProduct, content: string) => {
    await createQueueItem({
      title: product.title.slice(0, 500),
      content,
      status: "draft",
      image_url: product.image_url,
      button_text: product.affiliate_url || product.product_url ? "اشتري الآن" : undefined,
      button_url: product.affiliate_url ?? product.product_url,
    });
  };

  const handleAddToQueue = async (products: DiscoveryProduct[]) => {
    if (products.length === 0) return;
    setBatchBusy(true);
    setActionError(null);
    try {
      for (const product of products) {
        const content = [product.title, product.description ?? "", product.product_url]
          .filter(Boolean)
          .join("\n\n");
        await queueDraftFromProduct(product, content);
      }
      setActionMessage(`تمت إضافة ${products.length.toLocaleString("ar")} مسودة إلى قائمة النشر.`);
      selection.clear();
    } catch (error) {
      setActionError(getApiErrorMessage(error, "تعذر الإضافة إلى قائمة النشر."));
    } finally {
      setBatchBusy(false);
    }
  };

  const handleGenerateAi = async (products: DiscoveryProduct[]) => {
    if (products.length === 0) return;
    if (products.length === 1) {
      const product = products[0];
      router.push(`/ai?url=${encodeURIComponent(product.product_url)}`);
      return;
    }
    setBatchBusy(true);
    setActionError(null);
    try {
      let success = 0;
      for (const product of products) {
        const generated = await generateContent({ url: product.product_url });
        await queueDraftFromProduct(product, generated.content);
        success += 1;
      }
      setActionMessage(`تم توليد AI وإضافة ${success.toLocaleString("ar")} مسودة إلى القائمة.`);
      selection.clear();
    } catch (error) {
      setActionError(getApiErrorMessage(error, "تعذر توليد المحتوى."));
    } finally {
      setBatchBusy(false);
    }
  };

  const handleExport = () => {
    const rows = selection.selectedProducts.length > 0 ? selection.selectedProducts : filteredItems;
    if (rows.length === 0) return;
    exportDiscoveryProductsCsv(rows, `discovery-export-${Date.now()}.csv`);
    setActionMessage(`تم تصدير ${rows.length.toLocaleString("ar")} منتج.`);
  };

  const toggleColumn = (column: DiscoveryTableColumn) => {
    if (column === "product" || column === "actions") return;
    const current = uiPrefs.visibleColumns;
    const next = current.includes(column)
      ? current.filter((item) => item !== column)
      : [...current, column];
    updateUiPrefs({
      visibleColumns: next.length ? next : DEFAULT_VISIBLE_COLUMNS,
    });
  };

  const switchMode = (mode: DiscoveryMode) => {
    updateDraft({
      mode,
      category_id: mode === "category" ? draft.category_id : undefined,
      page: 1,
    });
  };

  const showInitialEmpty = hydrated && !session.lastResponse && !shouldFetch && !discovery.isFetching;
  const showLoading = discovery.isFetching || session.lastRunStatus === "running";
  const showError =
    !discovery.isFetching &&
    ((runToken > 0 && discovery.isError) || session.lastRunStatus === "error") &&
    items.length === 0;

  return (
    <PageContainer>
      <DiscoveryHeader
        lastRunAt={session.lastRunAt}
        lastRunStatus={
          session.lastRunStatus === "running" && discovery.isFetching
            ? "running"
            : session.lastRunStatus
        }
        canRun={!draftError && !discovery.isFetching}
        running={discovery.isFetching}
        onRun={() => runDiscovery({ ...draft, page: 1 })}
        totalDiscovered={response?.total ?? 0}
        pendingReview={pendingReview}
        importedCount={session.importedIds.length}
      />

      <div className="mt-4 space-y-3">
        <DiscoveryIntentTabs
          value={draft.mode ?? "hot"}
          onChange={(mode) =>
            updateDraft({
              mode,
              category_id: mode === "category" ? draft.category_id : undefined,
              page: 1,
            })
          }
        />
      </div>

      <div className="mt-4 space-y-4" aria-label="نتائج الاكتشاف">
        <DiscoveryFilterBar
          params={draft}
          categories={categories.data?.items ?? []}
          totalProducts={response?.total ?? null}
          onChange={updateDraft}
          onOpenAdvanced={() => setAdvancedOpen(true)}
        />

        {!canImport && (
          <p className="text-sm text-muted-foreground">
            الاستيراد متاح لحسابات المدير فقط. يمكنك المراجعة والتصدير وإعداد المحتوى ضمن صلاحياتك.
          </p>
        )}
        {actionError && (
          <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
            {actionError}
          </p>
        )}
        {actionMessage && (
          <p className="rounded-md bg-emerald-500/10 p-3 text-sm text-emerald-700" role="status">
            {actionMessage}
          </p>
        )}

        <DiscoveryResultsToolbar
          response={response}
          search={uiPrefs.resultSearch}
          density={uiPrefs.density}
          visibleColumns={uiPrefs.visibleColumns}
          refreshing={discovery.isFetching}
          onSearchChange={(value) => updateUiPrefs({ resultSearch: value })}
          onDensityChange={(value) => updateUiPrefs({ density: value })}
          onToggleColumn={toggleColumn}
          onRefresh={() => committed && runDiscovery(committed)}
          onPageChange={onPageChange}
        />

        {showInitialEmpty ? (
          <DiscoveryEmptyState
            variant="initial"
            onRun={() => runDiscovery({ ...draft, page: 1 })}
            onResetFilters={resetDraftFilters}
            onSwitchMode={switchMode}
          />
        ) : showLoading && items.length === 0 ? (
          <LoadingState rows={8} />
        ) : showError ? (
          <ErrorState
            message={session.lastError ?? "تعذر تشغيل الاكتشاف."}
            onRetry={() => committed && runDiscovery(committed)}
          />
        ) : items.length === 0 ? (
          <DiscoveryEmptyState
            variant="no-results"
            onRun={() => runDiscovery({ ...draft, page: 1 })}
            onResetFilters={resetDraftFilters}
            onSwitchMode={switchMode}
          />
        ) : filteredItems.length === 0 ? (
          <DiscoveryEmptyState
            variant="no-results"
            onRun={() => updateUiPrefs({ resultSearch: "" })}
            onResetFilters={() => updateUiPrefs({ resultSearch: "" })}
            onSwitchMode={switchMode}
          />
        ) : (
          <DiscoveryResultsTable
            items={filteredItems}
            selectedIds={selection.selectedIds}
            allSelected={selection.allSelected}
            importedIds={importedIds}
            canImport={canImport}
            importingId={
              singleImport.isPending && typeof singleImport.variables === "string"
                ? singleImport.variables
                : null
            }
            density={uiPrefs.density}
            visibleColumns={uiPrefs.visibleColumns}
            view="table"
            onToggle={selection.toggle}
            onToggleAll={selection.toggleAll}
            onInspect={(product) => setInspectorId(product.aliexpress_product_id)}
            onImport={(product) => void handleImportOne(product)}
            onGenerateAi={(product) => void handleGenerateAi([product])}
            onAddToQueue={(product) => void handleAddToQueue([product])}
          />
        )}

        <DiscoverySelectionBar
          count={selection.selectedIds.length}
          canImport={canImport}
          busy={batchBusy}
          onClear={selection.clear}
          onImport={() => void handleImportSelected()}
          onGenerateAi={() => void handleGenerateAi(selection.selectedProducts)}
          onAddToQueue={() => void handleAddToQueue(selection.selectedProducts)}
          onExport={handleExport}
        />
      </div>

      <DiscoveryAdvancedFiltersDrawer
        open={advancedOpen}
        params={draft}
        onClose={() => setAdvancedOpen(false)}
        onChange={updateDraft}
        onApply={() => runDiscovery({ ...draft, page: 1 })}
        onReset={resetDraftFilters}
      />

      <DiscoveryProductInspector
        product={inspectorProduct}
        open={inspectorProduct != null}
        canImport={canImport && !importedIds.has(inspectorProduct?.aliexpress_product_id ?? "")}
        importing={
          singleImport.isPending &&
          singleImport.variables === inspectorProduct?.aliexpress_product_id
        }
        onClose={() => setInspectorId(null)}
        onImport={(product) => void handleImportOne(product)}
        onGenerateAi={(product) => void handleGenerateAi([product])}
        onAddToQueue={(product) => void handleAddToQueue([product])}
      />
    </PageContainer>
  );
}

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
  imageSearchFingerprint,
  rememberImageSearchBody,
  useDiscoveryQuery,
  useDiscoverySelection,
  useDiscoverySession,
  useImageSearchQuery,
  useImportProduct,
  useImportProductsBatch,
} from "../hooks/useDiscovery";
import type {
  DiscoveryMode,
  DiscoveryParams,
  DiscoveryProduct,
  DiscoveryTableColumn,
  ProductImageSearchKey,
  ProductImageSearchRequest,
} from "../types/api";
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
import { ImageSearchPanel } from "./ImageSearchPanel";

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
  const [imageSearchInput, setImageSearchInput] = useState<ProductImageSearchKey | null>(null);

  const draft = session.draftParams;
  const committed = session.committedParams;
  const uiPrefs = normalizeUiPrefs(session.uiPrefs);
  const imageSearchActive = imageSearchInput != null;
  const shouldFetch = !imageSearchActive && runToken > 0 && committed != null;
  const discovery = useDiscoveryQuery(committed, shouldFetch);
  const imageSearch = useImageSearchQuery(imageSearchInput, imageSearchActive);
  const singleImport = useImportProduct();
  const batchImport = useImportProductsBatch();

  const canImport = currentUser.data?.role === "admin";
  const draftError = validateDiscoveryDraft(draft);

  useEffect(() => {
    if (imageSearchActive) return;
    if (!discovery.isFetching && runToken > 0 && committed) {
      if (discovery.isSuccess && discovery.data) {
        markSuccess(committed, discovery.data);
      } else if (discovery.isError) {
        markError(getApiErrorMessage(discovery.error, "تعذر تشغيل الاكتشاف."));
      }
    }
  }, [
    imageSearchActive,
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

  useEffect(() => {
    if (!imageSearchActive || imageSearch.isFetching || !imageSearchInput) return;
    if (imageSearch.isSuccess && imageSearch.data) {
      markSuccess(
        {
          mode: committed?.mode ?? draft.mode ?? "hot",
          page: imageSearchInput.page,
          page_size: 20,
        },
        imageSearch.data,
      );
    } else if (imageSearch.isError) {
      markError(getApiErrorMessage(imageSearch.error, "تعذر البحث بالصورة."));
    }
  }, [
    imageSearchActive,
    imageSearch.isFetching,
    imageSearch.isSuccess,
    imageSearch.isError,
    imageSearch.data,
    imageSearch.error,
    imageSearchInput,
    committed?.mode,
    draft.mode,
    markSuccess,
    markError,
  ]);

  const items = useMemo(() => {
    if (imageSearchActive) {
      return imageSearch.data?.items ?? [];
    }
    if (discovery.isSuccess && discovery.data) return discovery.data.items;
    return session.lastResponse?.items ?? [];
  }, [
    imageSearchActive,
    imageSearch.data,
    discovery.isSuccess,
    discovery.data,
    session.lastResponse,
  ]);

  const filteredItems = useMemo(() => {
    const q = uiPrefs.resultSearch.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => item.title.toLowerCase().includes(q));
  }, [items, uiPrefs.resultSearch]);

  const response = imageSearchActive
    ? (imageSearch.data ?? session.lastResponse)
    : (discovery.data ?? session.lastResponse);
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
      setImageSearchInput(null);
      const next = { ...params, page: params.page ?? 1, page_size: params.page_size ?? 20 };
      markRunning(next);
      setRunToken((value) => value + 1);
      clearSelection();
    },
    [draft, markRunning, clearSelection],
  );

  const runImageSearch = useCallback(
    (payload: ProductImageSearchRequest, file?: File) => {
      setActionError(null);
      setActionMessage(null);
      setInspectorId(null);
      const page = payload.page ?? 1;
      let next: ProductImageSearchKey;
      if (payload.image_url) {
        next = { source: "url", image_url: payload.image_url, page };
      } else if (payload.image_base64 && file) {
        const fingerprint = imageSearchFingerprint(file);
        rememberImageSearchBody(fingerprint, payload.image_base64);
        next = { source: "upload", fingerprint, page };
      } else {
        setActionError("أدخل رابط صورة أو ارفع ملفًا.");
        return;
      }
      setImageSearchInput((prev) => {
        if (
          prev &&
          prev.source === next.source &&
          prev.image_url === next.image_url &&
          prev.fingerprint === next.fingerprint &&
          prev.page === next.page
        ) {
          return prev;
        }
        return next;
      });
      markRunning({
        mode: draft.mode ?? "hot",
        page,
        page_size: 20,
      });
      clearSelection();
    },
    [draft.mode, markRunning, clearSelection],
  );

  const onPageChange = (page: number) => {
    if (imageSearchInput) {
      setImageSearchInput({ ...imageSearchInput, page });
      return;
    }
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

  const activeFetching = imageSearchActive ? imageSearch.isFetching : discovery.isFetching;
  const showInitialEmpty =
    hydrated &&
    !session.lastResponse &&
    !shouldFetch &&
    !imageSearchActive &&
    !activeFetching;
  const showLoading = activeFetching || session.lastRunStatus === "running";
  const showError =
    !activeFetching &&
    ((imageSearchActive && imageSearch.isError) ||
      (!imageSearchActive && runToken > 0 && discovery.isError) ||
      session.lastRunStatus === "error") &&
    items.length === 0;
  const showNoImages =
    imageSearchActive &&
    !activeFetching &&
    imageSearch.isSuccess &&
    items.length === 0;

  return (
    <PageContainer>
      <DiscoveryHeader
        lastRunAt={session.lastRunAt}
        lastRunStatus={
          session.lastRunStatus === "running" && activeFetching
            ? "running"
            : session.lastRunStatus
        }
        canRun={!draftError && !activeFetching}
        running={activeFetching}
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
        <ImageSearchPanel searching={imageSearch.isFetching} onSearch={runImageSearch} />
        {imageSearchActive ? (
          <p className="text-sm text-muted-foreground">نتائج البحث بالصورة من الكتالوج العالمي.</p>
        ) : null}
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
          refreshing={activeFetching}
          onSearchChange={(value) => updateUiPrefs({ resultSearch: value })}
          onDensityChange={(value) => updateUiPrefs({ density: value })}
          onToggleColumn={toggleColumn}
          onRefresh={() => {
            if (imageSearchInput) {
              void imageSearch.refetch();
              return;
            }
            if (committed) runDiscovery(committed);
          }}
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
            onRetry={() => {
              if (imageSearchInput) {
                void imageSearch.refetch();
                return;
              }
              if (committed) runDiscovery(committed);
            }}
          />
        ) : showNoImages ? (
          <DiscoveryEmptyState
            variant="no-images"
            onRun={() => {
              if (imageSearchInput) void imageSearch.refetch();
            }}
            onResetFilters={() => {
              setImageSearchInput(null);
              resetDraftFilters();
            }}
            onSwitchMode={switchMode}
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
        onSearchByImage={(imageUrl) =>
          runImageSearch({ image_url: imageUrl, page: 1, page_size: 20 })
        }
      />
    </PageContainer>
  );
}

"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/states";
import { ToastOverlay } from "@/components/common/ToastOverlay";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Button } from "@/components/ui/primitives";
import { useCurrentUser } from "@/features/auth/hooks/useAuth";
import { useCreateQueueItem, useQueue } from "@/features/queue/hooks/useQueue";
import { exportProductsCsv } from "../lib/export";
import { getProductPipelineState, indexQueueByProduct } from "../lib/inventory";
import {
  useDeleteProduct,
  useProductInventoryState,
  useProducts,
  useUpdateProduct,
} from "../hooks/useProducts";
import type { Product, ProductStatus } from "../types/api";
import { DeleteProductsDialog } from "./DeleteProductsDialog";
import { ProductDetailsDrawer } from "./ProductDetailsDrawer";
import { ProductsSelectionBar } from "./ProductsSelectionBar";
import { ProductsTable } from "./ProductsTable";
import { ProductsToolbar } from "./ProductsToolbar";

export function ProductsView() {
  const router = useRouter();
  const currentUser = useCurrentUser();
  const [status, setStatus] = useState<ProductStatus | "">("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [activeProduct, setActiveProduct] = useState<Product | null>(null);
  const [deleteTargets, setDeleteTargets] = useState<Product[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const products = useProducts({
    status: status || undefined,
    skip: page * pageSize,
    limit: pageSize,
  });
  const queue = useQueue(undefined, 200);
  const updateProduct = useUpdateProduct();
  const deleteProduct = useDeleteProduct();
  const createQueue = useCreateQueueItem();
  const items = products.data?.items ?? [];
  const inventory = useProductInventoryState(items);
  const canManage = currentUser.data?.role === "admin";
  const queueIndex = useMemo(
    () => indexQueueByProduct(queue.data?.items ?? []),
    [queue.data?.items],
  );
  const busy =
    updateProduct.isPending || deleteProduct.isPending || createQueue.isPending;

  const activePipelineState = activeProduct
    ? getProductPipelineState(activeProduct, queueIndex)
    : null;

  const sendToAi = (product: Product) => {
    router.push(`/ai?product=${encodeURIComponent(product.id)}`);
  };

  const addProductsToQueue = async (selected: Product[]) => {
    if (selected.length === 0) return;
    setActionError(null);
    try {
      for (const product of selected) {
        await createQueue.mutateAsync({
          title: product.title,
          content: [product.title, product.description, product.affiliate_url ?? product.product_url]
            .filter(Boolean)
            .join("\n\n"),
          status: "queued",
          product_id: product.id,
          image_url: product.image_url || undefined,
          button_text: "اشتري الآن",
          button_url: product.affiliate_url ?? product.product_url,
        });
      }
      setActionMessage(
        `تمت إضافة ${selected.length.toLocaleString("ar")} منتج إلى قائمة النشر.`,
      );
      inventory.clearSelection();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "تعذر إضافة المنتجات إلى القائمة.");
    }
  };

  const changeSelectedStatus = async (nextStatus: ProductStatus) => {
    setActionError(null);
    try {
      for (const product of inventory.selectedProducts) {
        await updateProduct.mutateAsync({ id: product.id, status: nextStatus });
      }
      setActionMessage("تم تحديث حالة المنتجات المحددة.");
      inventory.clearSelection();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "تعذر تحديث الحالة.");
    }
  };

  const confirmDelete = async () => {
    setActionError(null);
    try {
      for (const product of deleteTargets) {
        await deleteProduct.mutateAsync(product.id);
      }
      setActionMessage(
        `تم حذف ${deleteTargets.length.toLocaleString("ar")} منتج من المخزون.`,
      );
      if (deleteTargets.some((product) => product.id === activeProduct?.id)) {
        setActiveProduct(null);
      }
      inventory.clearSelection();
      setDeleteTargets([]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "تعذر حذف المنتجات.");
    }
  };

  const hasSearch = inventory.clientSearch.trim().length > 0;
  const isEmptyInventory = !products.isPending && !products.isError && items.length === 0 && !status;
  const isFilteredEmpty =
    !products.isPending &&
    !products.isError &&
    (inventory.filteredItems.length === 0 || (items.length === 0 && Boolean(status)));

  return (
    <PageContainer wide>
      <PageHeader
        title="مخزون المنتجات"
        description="راجع المنتجات المستوردة ونظّم انتقالها إلى المحتوى وقائمة النشر."
        actions={
          <Link href="/discovery">
            <Button variant="outline">استيراد من الاكتشاف</Button>
          </Link>
        }
      />

      <div className="mt-4 space-y-4">
        <ProductsToolbar
          search={inventory.clientSearch}
          status={status}
          sort={inventory.sort}
          density={inventory.tableDensity}
          visibleColumns={inventory.visibleColumns}
          pageSize={pageSize}
          productCount={products.data?.total ?? 0}
          refreshing={products.isFetching}
          onSearchChange={(value) => {
            inventory.setClientSearch(value);
            inventory.clearSelection();
          }}
          onStatusChange={(value) => {
            setStatus(value);
            setPage(0);
            inventory.clearSelection();
          }}
          onSortChange={inventory.setSort}
          onDensityChange={inventory.setTableDensity}
          onToggleColumn={inventory.toggleColumn}
          onPageSizeChange={(value) => {
            setPageSize(value);
            setPage(0);
            inventory.clearSelection();
          }}
          onRefresh={() => {
            void products.refetch();
            void queue.refetch();
          }}
        />

        {products.isPending ? (
          <LoadingState rows={8} />
        ) : products.isError ? (
          <ErrorState
            message="تعذر تحميل مخزون المنتجات."
            onRetry={() => void products.refetch()}
          />
        ) : isEmptyInventory ? (
          <EmptyState
            title="مخزون المنتجات فارغ"
            description="ابدأ من مساحة الاكتشاف، راجع المنتجات المرشحة، ثم استورد المناسب منها إلى المخزون."
            action={
              <Link href="/discovery">
                <Button>بدء الاكتشاف</Button>
              </Link>
            }
          />
        ) : isFilteredEmpty ? (
          <EmptyState
            title={hasSearch ? "لا توجد نتائج للبحث" : "لا توجد منتجات بهذه الحالة"}
            description={
              hasSearch
                ? "جرّب عنوانًا أو فئة أو متجرًا أو SKU مختلفًا، أو امسح البحث."
                : "غيّر تصفية الحالة لعرض بقية منتجات المخزون."
            }
            action={
              <Button
                variant="outline"
                onClick={() => {
                  inventory.setClientSearch("");
                  setStatus("");
                  setPage(0);
                }}
              >
                مسح عوامل التصفية
              </Button>
            }
          />
        ) : (
          <>
            <ProductsTable
              items={inventory.filteredItems}
              selectedProductIds={inventory.selectedProductIds}
              allSelected={inventory.allVisibleSelected}
              density={inventory.tableDensity}
              visibleColumns={inventory.visibleColumns}
              queueIndex={queueIndex}
              canManage={canManage}
              onToggle={inventory.toggle}
              onToggleAll={inventory.toggleAll}
              onPreview={setActiveProduct}
              onGenerate={sendToAi}
              onDelete={(product) => setDeleteTargets([product])}
            />

            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                عرض {(page * pageSize + 1).toLocaleString("ar")}–
                {Math.min((page + 1) * pageSize, products.data.total).toLocaleString("ar")} من{" "}
                {products.data.total.toLocaleString("ar")}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  disabled={page === 0}
                  onClick={() => {
                    setPage((value) => value - 1);
                    inventory.clearSelection();
                  }}
                >
                  السابق
                </Button>
                <Button
                  variant="outline"
                  disabled={(page + 1) * pageSize >= products.data.total}
                  onClick={() => {
                    setPage((value) => value + 1);
                    inventory.clearSelection();
                  }}
                >
                  التالي
                </Button>
              </div>
            </div>
          </>
        )}

        <ProductsSelectionBar
          count={inventory.selectedProductIds.length}
          busy={busy}
          canManage={canManage}
          onClear={inventory.clearSelection}
          onDelete={() => setDeleteTargets(inventory.selectedProducts)}
          onChangeStatus={(nextStatus) => void changeSelectedStatus(nextStatus)}
          onSendToAi={() => {
            const product = inventory.selectedProducts[0];
            if (product) sendToAi(product);
          }}
          onMoveToQueue={() => void addProductsToQueue(inventory.selectedProducts)}
          onExport={() => exportProductsCsv(inventory.selectedProducts)}
        />
      </div>

      <ProductDetailsDrawer
        product={activeProduct}
        pipelineState={activePipelineState}
        open={activeProduct != null}
        onClose={() => setActiveProduct(null)}
        onGenerateContent={sendToAi}
        onAddToQueue={(product) => void addProductsToQueue([product])}
      />

      <DeleteProductsDialog
        count={deleteTargets.length}
        open={deleteTargets.length > 0}
        busy={deleteProduct.isPending}
        onCancel={() => setDeleteTargets([])}
        onConfirm={() => void confirmDelete()}
      />

      <ToastOverlay
        message={actionError ?? actionMessage}
        tone={actionError ? "error" : "success"}
        onDismiss={() => {
          setActionError(null);
          setActionMessage(null);
        }}
      />
    </PageContainer>
  );
}

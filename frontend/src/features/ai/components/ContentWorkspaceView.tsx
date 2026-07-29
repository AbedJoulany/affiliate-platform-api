"use client";

import { useMemo, useState } from "react";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { useCreateQueueItem, usePublishQueueItem } from "@/features/queue/hooks/useQueue";
import { useContentSession } from "../hooks/useContentSession";
import { useGenerateContent } from "../hooks/useGenerateContent";
import { downloadContent } from "../lib/export";
import { AiSuggestionsPanel } from "./AiSuggestionsPanel";
import { ConfigControlBoard } from "./ConfigControlBoard";
import { DistributionHub } from "./DistributionHub";
import { PerformanceScoreBadges } from "./PerformanceScoreBadges";
import { ResetStudioDialog } from "./ResetStudioDialog";
import { RichDocumentCanvas } from "./RichDocumentCanvas";
import { VariantCompareDialog } from "./VariantCompareDialog";
import { VariantTabs } from "./VariantTabs";

export function ContentWorkspaceView({
  initialProductId,
  initialUrl,
}: {
  initialProductId?: string;
  initialUrl?: string;
}) {
  const sessionApi = useContentSession({
    productId: initialProductId,
    url: initialUrl,
  });
  const generation = useGenerateContent();
  const createQueue = useCreateQueueItem();
  const publishQueue = usePublishQueueItem();
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);

  const { session, activeVariant } = sessionApi;
  const busy = createQueue.isPending || publishQueue.isPending;
  const hasVariants = session.variants.length > 0;

  const canGenerate = useMemo(() => {
    if (session.productContext.sourceType === "product") {
      return Boolean(session.productContext.productId);
    }
    return Boolean(session.productContext.url?.trim());
  }, [session.productContext]);

  const comparePair = useMemo(() => {
    if (session.variants.length < 2) return { left: null, right: null };
    const activeIndex = session.variants.findIndex(
      (item) => item.id === session.activeVariantId,
    );
    const right = session.variants[activeIndex >= 0 ? activeIndex : session.variants.length - 1];
    const left =
      session.variants[activeIndex > 0 ? activeIndex - 1 : session.variants.length - 2] ?? null;
    return { left, right };
  }, [session.variants, session.activeVariantId]);

  const runGenerate = (origin: "generate" | "variant" = "generate") => {
    const payload = sessionApi.buildGeneratePayload();
    if (!payload) {
      setActionError("اختر منتجًا أو الصق رابط AliExpress قبل التوليد.");
      return;
    }
    setActionError(null);
    setActionMessage(null);
    generation.mutate(payload, {
      onSuccess: (data) => {
        sessionApi.appendVariantFromResponse(
          data,
          session.variants.length === 0 ? "generate" : origin,
        );
        setActionMessage(
          session.variants.length === 0
            ? "تم إنشاء النسخة الأولى."
            : "تم توليد نسخة بديلة وإضافتها إلى السجل.",
        );
      },
      onError: (error) => {
        setActionError(error.message || "تعذر توليد المحتوى.");
      },
    });
  };

  const performReset = () => {
    sessionApi.resetStudio();
    generation.reset();
    setActionError(null);
    setActionMessage(null);
    setCompareOpen(false);
    setResetConfirmOpen(false);
  };

  const requestReset = () => {
    if (session.variants.length > 0) {
      setResetConfirmOpen(true);
      return;
    }
    performReset();
  };

  const queueFromActive = async (status: "draft" | "queued", thenPublish = false) => {
    if (!activeVariant?.content.trim()) return;
    setActionError(null);
    try {
      const item = await createQueue.mutateAsync({
        content: activeVariant.content.trim(),
        status,
        product_id: activeVariant.productId,
        title: session.productContext.productLabel ?? undefined,
      });
      sessionApi.logDistribution(
        status === "draft" ? "draft_saved" : "queued",
        activeVariant.id,
      );
      if (thenPublish) {
        await publishQueue.mutateAsync(item.id);
        sessionApi.logDistribution("published", activeVariant.id);
        setActionMessage("تم النشر الآن عبر قائمة النشر.");
      } else {
        setActionMessage(
          status === "draft" ? "تم حفظ المسودة." : "تمت الإضافة إلى جدولة النشر.",
        );
      }
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "تعذر إتمام العملية.");
    }
  };

  return (
    <PageContainer>
      <PageHeader
        title="مساحة محتوى التسويق"
        description="جلسة محتوى متكاملة: إعداد → توليد نسخ → تحرير → توزيع."
      />

      {/*
        RTL note: ConfigControlBoard is the FIRST grid child so it locks to the
        visual right under dir="rtl". Canvas is the second child (visual left).
      */}
      <div className="mt-4 grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
        <ConfigControlBoard
          session={session}
          error={actionError ?? (generation.isError ? generation.error.message : null)}
          onProductContextChange={sessionApi.updateProductContext}
          onConfigChange={sessionApi.updateConfig}
          onToggleAdvanced={() => sessionApi.setAdvancedOpen(!session.advancedOpen)}
        />

        <section className="min-w-0 space-y-4" aria-label="مساحة المستند">
          {actionMessage ? (
            <p className="rounded-md bg-emerald-500/10 p-3 text-sm text-emerald-700" role="status">
              {actionMessage}
            </p>
          ) : null}

          <VariantTabs
            variants={session.variants}
            activeVariantId={session.activeVariantId}
            onActivate={sessionApi.activateVariant}
            onCompare={() => {
              if (session.variants.length >= 2) setCompareOpen(true);
            }}
            onRestorePrevious={() => {
              const activeIndex = session.variants.findIndex(
                (item) => item.id === session.activeVariantId,
              );
              if (activeIndex > 0) {
                sessionApi.restoreVariant(session.variants[activeIndex - 1].id);
              }
            }}
          />

          {activeVariant ? <PerformanceScoreBadges scores={activeVariant.scores} /> : null}

          <RichDocumentCanvas
            content={activeVariant?.content ?? ""}
            onChange={sessionApi.updateActiveContent}
          />

          <AiSuggestionsPanel
            open={session.suggestionsOpen}
            activeModifiers={session.prompt.instructionModifiers}
            onToggleOpen={() => sessionApi.setSuggestionsOpen(!session.suggestionsOpen)}
            onToggleModifier={sessionApi.toggleModifier}
            onApplyVariant={() => runGenerate("variant")}
            applying={generation.isPending}
          />

          <DistributionHub
            disabled={!activeVariant?.content.trim()}
            busy={busy}
            generating={generation.isPending}
            canGenerate={canGenerate}
            hasVariants={hasVariants}
            onGenerate={() => runGenerate("generate")}
            onPublishNow={() => void queueFromActive("queued", true)}
            onAddToQueue={() => void queueFromActive("queued")}
            onSaveDraft={() => void queueFromActive("draft")}
            onRegenerate={() => runGenerate("variant")}
            onReset={requestReset}
            onCopy={() => {
              if (!activeVariant) return;
              void navigator.clipboard.writeText(activeVariant.content);
              setActionMessage("تم نسخ النص الحالي.");
            }}
            onExport={(format) => {
              if (!activeVariant) return;
              downloadContent(activeVariant.content, format);
              sessionApi.logDistribution("exported", activeVariant.id);
              setActionMessage(`تم تصدير الملف .${format}`);
            }}
          />
        </section>
      </div>

      <VariantCompareDialog
        open={compareOpen}
        left={comparePair.left}
        right={comparePair.right}
        onClose={() => setCompareOpen(false)}
      />

      <ResetStudioDialog
        open={resetConfirmOpen}
        onCancel={() => setResetConfirmOpen(false)}
        onConfirm={performReset}
      />
    </PageContainer>
  );
}

/** @deprecated Use ContentWorkspaceView */
export function AIStudioView(props: {
  initialProductId?: string;
  initialUrl?: string;
}) {
  return <ContentWorkspaceView {...props} />;
}

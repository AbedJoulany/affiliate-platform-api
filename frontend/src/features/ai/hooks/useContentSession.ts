"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { GenerateContentResponse, InstructionModifier } from "../types/api";
import type {
  ContentSession,
  ContentVariant,
  ContentVariantOrigin,
  ProductContextState,
  SessionConfig,
} from "../types/session";
import { parseMarketingDocument } from "../lib/document";
import { scoreContent } from "../lib/scores";
import {
  createEmptySession,
  loadContentSession,
  saveContentSession,
  clearContentSession,
} from "../lib/session";

function touch(session: ContentSession): ContentSession {
  return { ...session, updatedAt: new Date().toISOString() };
}

function buildVariant(
  session: ContentSession,
  response: GenerateContentResponse,
  origin: ContentVariantOrigin,
): ContentVariant {
  const index = session.variants.length + 1;
  return {
    id: crypto.randomUUID(),
    index,
    createdAt: new Date().toISOString(),
    content: response.content,
    structured: parseMarketingDocument(response.content),
    scores: scoreContent(response.content, session.config.language),
    configSnapshot: { ...session.config },
    modifiersSnapshot: [...session.prompt.instructionModifiers],
    provider: response.provider,
    productId: response.product_id,
    sourceUrl: response.source_url,
    origin,
  };
}

export function useContentSession(initial?: {
  productId?: string;
  url?: string;
}) {
  const [session, setSession] = useState<ContentSession>(() => {
    const loaded = loadContentSession();
    if (initial?.productId) {
      return {
        ...loaded,
        productContext: {
          sourceType: "product",
          productId: initial.productId,
          productLabel: loaded.productContext.productLabel,
          url: null,
        },
      };
    }
    if (initial?.url) {
      return {
        ...loaded,
        productContext: {
          sourceType: "url",
          productId: null,
          productLabel: null,
          url: initial.url,
        },
      };
    }
    return loaded;
  });
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveContentSession(session);
  }, [session, hydrated]);

  const activeVariant = useMemo(
    () => session.variants.find((item) => item.id === session.activeVariantId) ?? null,
    [session.variants, session.activeVariantId],
  );

  const updateProductContext = useCallback((patch: Partial<ProductContextState>) => {
    setSession((prev) =>
      touch({
        ...prev,
        productContext: { ...prev.productContext, ...patch },
      }),
    );
  }, []);

  const updateConfig = useCallback((patch: Partial<SessionConfig>) => {
    setSession((prev) => {
      const config = { ...prev.config, ...patch };
      const at = new Date().toISOString();
      return touch({
        ...prev,
        config,
        history: [...prev.history, { type: "config_changed", at, config }],
      });
    });
  }, []);

  const toggleModifier = useCallback((modifier: InstructionModifier) => {
    setSession((prev) => {
      const enabled = !prev.prompt.instructionModifiers.includes(modifier);
      const instructionModifiers = enabled
        ? [...prev.prompt.instructionModifiers, modifier]
        : prev.prompt.instructionModifiers.filter((item) => item !== modifier);
      const at = new Date().toISOString();
      return touch({
        ...prev,
        prompt: { instructionModifiers },
        history: [
          ...prev.history,
          { type: "modifier_toggled", at, modifier, enabled },
        ],
      });
    });
  }, []);

  const setSuggestionsOpen = useCallback((open: boolean) => {
    setSession((prev) => touch({ ...prev, suggestionsOpen: open }));
  }, []);

  const setAdvancedOpen = useCallback((open: boolean) => {
    setSession((prev) => touch({ ...prev, advancedOpen: open }));
  }, []);

  const setCompareVariantIds = useCallback((ids: [string, string] | null) => {
    setSession((prev) => touch({ ...prev, compareVariantIds: ids }));
  }, []);

  const activateVariant = useCallback((variantId: string) => {
    setSession((prev) => {
      if (!prev.variants.some((item) => item.id === variantId)) return prev;
      const at = new Date().toISOString();
      return touch({
        ...prev,
        activeVariantId: variantId,
        history: [...prev.history, { type: "variant_activated", at, variantId }],
      });
    });
  }, []);

  const appendVariantFromResponse = useCallback(
    (response: GenerateContentResponse, origin: ContentVariantOrigin = "generate") => {
      setSession((prev) => {
        const variant = buildVariant(prev, response, origin);
        const at = new Date().toISOString();
        return touch({
          ...prev,
          variants: [...prev.variants, variant],
          activeVariantId: variant.id,
          history: [
            ...prev.history,
            { type: "variant_generated", at, variantId: variant.id },
            { type: "variant_activated", at, variantId: variant.id },
          ],
        });
      });
    },
    [],
  );

  const updateActiveContent = useCallback((content: string) => {
    setSession((prev) => {
      if (!prev.activeVariantId) return prev;
      return touch({
        ...prev,
        variants: prev.variants.map((variant) =>
          variant.id === prev.activeVariantId
            ? {
                ...variant,
                content,
                structured: parseMarketingDocument(content),
                scores: scoreContent(content, prev.config.language),
                origin: "manual_edit" as const,
              }
            : variant,
        ),
      });
    });
  }, []);

  const restoreVariant = useCallback((fromVariantId: string) => {
    setSession((prev) => {
      const source = prev.variants.find((item) => item.id === fromVariantId);
      if (!source) return prev;
      const at = new Date().toISOString();
      const restored: ContentVariant = {
        ...source,
        id: crypto.randomUUID(),
        index: prev.variants.length + 1,
        createdAt: at,
        origin: "restore",
      };
      return touch({
        ...prev,
        variants: [...prev.variants, restored],
        activeVariantId: restored.id,
        history: [
          ...prev.history,
          {
            type: "variant_restored",
            at,
            fromVariantId,
            newVariantId: restored.id,
          },
          { type: "variant_activated", at, variantId: restored.id },
        ],
      });
    });
  }, []);

  const logDistribution = useCallback(
    (type: "exported" | "queued" | "published" | "draft_saved", variantId: string) => {
      setSession((prev) =>
        touch({
          ...prev,
          history: [
            ...prev.history,
            { type, at: new Date().toISOString(), variantId },
          ],
        }),
      );
    },
    [],
  );

  const resetStudio = useCallback(() => {
    clearContentSession();
    setSession(createEmptySession());
  }, []);

  const buildGeneratePayload = useCallback(() => {
    const { productContext, config, prompt } = session;
    const base = {
      content_type: config.contentType,
      tone: config.tone,
      language: config.language,
      length: config.length,
      instruction_modifiers: prompt.instructionModifiers,
      ...(config.provider ? { provider: config.provider } : {}),
    };
    if (productContext.sourceType === "product" && productContext.productId) {
      return { ...base, product_id: productContext.productId };
    }
    if (productContext.url?.trim()) {
      return { ...base, url: productContext.url.trim() };
    }
    return null;
  }, [session]);

  return {
    session,
    hydrated,
    activeVariant,
    updateProductContext,
    updateConfig,
    toggleModifier,
    setSuggestionsOpen,
    setAdvancedOpen,
    setCompareVariantIds,
    activateVariant,
    appendVariantFromResponse,
    updateActiveContent,
    restoreVariant,
    logDistribution,
    resetStudio,
    /** @deprecated Prefer resetStudio */
    resetSession: resetStudio,
    buildGeneratePayload,
  };
}

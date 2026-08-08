import type { ContentSession, SessionConfig } from "../types/session";

const STORAGE_KEY = "affiliate_content_session_v1";

export function createEmptySession(
  seed?: Partial<Pick<ContentSession, "productContext">>,
): ContentSession {
  const now = new Date().toISOString();
  const config: SessionConfig = {
    contentType: "telegram",
    tone: "persuasive",
    language: "ar",
    length: "medium",
    provider: null,
  };

  return {
    id: crypto.randomUUID(),
    createdAt: now,
    updatedAt: now,
    productContext: seed?.productContext ?? {
      sourceType: "url",
      productId: null,
      productLabel: null,
      url: "",
    },
    config,
    prompt: { instructionModifiers: [] },
    variants: [],
    activeVariantId: null,
    history: [{ type: "session_created", at: now }],
    suggestionsOpen: false,
    advancedOpen: false,
    compareVariantIds: null,
  };
}

export function loadContentSession(): ContentSession {
  if (typeof window === "undefined") return createEmptySession();
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return createEmptySession();
    const parsed = JSON.parse(raw) as ContentSession;
    return {
      ...createEmptySession(),
      ...parsed,
      config: { ...createEmptySession().config, ...parsed.config },
      prompt: {
        instructionModifiers: parsed.prompt?.instructionModifiers ?? [],
      },
      variants: parsed.variants ?? [],
      history: parsed.history ?? [],
    };
  } catch {
    return createEmptySession();
  }
}

export function saveContentSession(session: ContentSession): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearContentSession(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(STORAGE_KEY);
}

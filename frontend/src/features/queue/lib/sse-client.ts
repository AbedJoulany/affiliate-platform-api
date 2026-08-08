/**
 * Fetch-based SSE client for the queue realtime stream.
 *
 * Public API: {@link createQueueEventStream}, {@link getQueueStreamUrl},
 * {@link computeReconnectDelayMs}, and related option/error types.
 *
 * ---------------------------------------------------------------------------
 * Vendored SSE wire-format parsing core
 * ---------------------------------------------------------------------------
 * The byte/line/message parsing below is adapted from
 * `@microsoft/fetch-event-source` (parse.ts), Copyright (c) Microsoft
 * Corporation, MIT License:
 * https://github.com/Azure/fetch-event-source/blob/main/src/parse.ts
 *
 * Copied into this module (not installed as an npm dependency) so we keep
 * proven SSE parsing without depending on an unmaintained package. Parser
 * internals are intentionally not exported for production consumers.
 * ---------------------------------------------------------------------------
 */

import type { QueueEventEnvelope } from "../types/events";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export type QueueSseErrorKind = "auth" | "network" | "server" | "abort" | "parse";

export type QueueSseError = {
  kind: QueueSseErrorKind;
  message: string;
  status?: number;
  /** When true, the client stops reconnecting (e.g. 401/403). */
  fatal: boolean;
};

export type CreateQueueEventStreamOptions = {
  token: string;
  signal: AbortSignal;
  onMessage: (event: QueueEventEnvelope) => void;
  onOpen?: () => void;
  onError?: (error: QueueSseError) => void;
  /** Fired before each reconnect sleep (attempt is 1-based after the first failure). */
  onReconnect?: (attempt: number, delayMs: number) => void;
  url?: string;
  lastEventId?: string;
  /** Override for tests. */
  fetchImpl?: typeof fetch;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  /** Override Math.random for deterministic backoff tests. */
  random?: () => number;
};

const DEFAULT_INITIAL_BACKOFF_MS = 1_000;
const DEFAULT_MAX_BACKOFF_MS = 30_000;

export function getQueueStreamUrl(): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
  return `${base.replace(/\/$/, "")}/queues/stream`;
}

/**
 * Exponential backoff with jitter, capped at `maxMs`.
 * Attempt 0 → ~1s, 1 → ~2s, 2 → ~4s, … capped at 30s by default.
 */
export function computeReconnectDelayMs(
  attemptIndex: number,
  initialMs = DEFAULT_INITIAL_BACKOFF_MS,
  maxMs = DEFAULT_MAX_BACKOFF_MS,
  random: () => number = Math.random,
): number {
  const exp = Math.min(initialMs * 2 ** Math.max(0, attemptIndex), maxMs);
  const jitter = random() * initialMs;
  return Math.min(Math.round(exp + jitter), maxMs);
}

/**
 * Open an authenticated SSE connection to the queue event stream.
 * Reconnects with exponential backoff until `signal` aborts or a fatal
 * auth error occurs. Does not use browser `EventSource` (no Auth headers).
 */
export async function createQueueEventStream(
  options: CreateQueueEventStreamOptions,
): Promise<void> {
  const {
    token,
    signal,
    onMessage,
    onOpen,
    onError,
    onReconnect,
    url = getQueueStreamUrl(),
    fetchImpl = fetch,
    lastEventId: initialLastEventId = "",
    initialBackoffMs = DEFAULT_INITIAL_BACKOFF_MS,
    maxBackoffMs = DEFAULT_MAX_BACKOFF_MS,
    random = Math.random,
  } = options;

  let lastEventId = initialLastEventId;
  let consecutiveFailures = 0;
  let serverRetryMs: number | undefined;

  while (!signal.aborted) {
    try {
      if (consecutiveFailures > 0) {
        const delay =
          serverRetryMs ??
          computeReconnectDelayMs(
            consecutiveFailures - 1,
            initialBackoffMs,
            maxBackoffMs,
            random,
          );
        serverRetryMs = undefined;
        onReconnect?.(consecutiveFailures, delay);
        await sleep(delay, signal);
        if (signal.aborted) break;
      }

      const headers: Record<string, string> = {
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
      };
      if (lastEventId) {
        headers["Last-Event-ID"] = lastEventId;
      }

      const response = await fetchImpl(url, {
        method: "GET",
        headers,
        signal,
      });

      if (!response.ok) {
        const status = response.status;
        if (status === 401 || status === 403) {
          onError?.({
            kind: "auth",
            status,
            message:
              status === 401
                ? "انتهت صلاحية الجلسة."
                : "غير مصرح بالوصول إلى بث الأحداث.",
            fatal: true,
          });
          return;
        }
        consecutiveFailures += 1;
        onError?.({
          kind: "server",
          status,
          message: `فشل بث الأحداث (${status}).`,
          fatal: false,
        });
        continue;
      }

      if (!response.body) {
        consecutiveFailures += 1;
        onError?.({
          kind: "network",
          message: "استجابة البث لا تحتوي على محتوى.",
          fatal: false,
        });
        continue;
      }

      consecutiveFailures = 0;
      onOpen?.();

      await consumeSseStream(response.body, signal, {
        onId: (id) => {
          if (id) lastEventId = id;
        },
        onRetry: (retry) => {
          serverRetryMs = retry;
        },
        onRawMessage: (raw) => {
          if (!raw.data) return;
          if (raw.id) lastEventId = raw.id;
          try {
            const parsed = JSON.parse(raw.data) as QueueEventEnvelope;
            onMessage(parsed);
          } catch {
            onError?.({
              kind: "parse",
              message: "تعذر قراءة حدث البث.",
              fatal: false,
            });
          }
        },
      });

      if (signal.aborted) break;

      consecutiveFailures += 1;
      onError?.({
        kind: "network",
        message: "انقطع بث الأحداث.",
        fatal: false,
      });
    } catch (error) {
      if (signal.aborted || isAbortError(error)) {
        onError?.({
          kind: "abort",
          message: "تم إلغاء بث الأحداث.",
          fatal: true,
        });
        return;
      }
      consecutiveFailures += 1;
      onError?.({
        kind: "network",
        message:
          error instanceof Error ? error.message : "تعذر الاتصال ببث الأحداث.",
        fatal: false,
      });
    }
  }
}

// ---------------------------------------------------------------------------
// Internals — stream consumption + vendored parser (not exported)
// ---------------------------------------------------------------------------

type RawSseMessage = {
  id: string;
  event: string;
  data: string;
  retry?: number;
};

async function consumeSseStream(
  stream: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  handlers: {
    onId: (id: string) => void;
    onRetry: (retry: number) => void;
    onRawMessage: (message: RawSseMessage) => void;
  },
): Promise<void> {
  await getBytes(
    stream,
    getLines(
      getMessages(handlers.onId, handlers.onRetry, handlers.onRawMessage),
    ),
    signal,
  );
}

function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      resolve();
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

/*
 * --- Begin vendored parsing core (adapted from @microsoft/fetch-event-source) ---
 */

/** @see https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events#Event_stream_format */
interface EventSourceMessage {
  id: string;
  event: string;
  data: string;
  retry?: number;
}

async function getBytes(
  stream: ReadableStream<Uint8Array>,
  onChunk: (arr: Uint8Array) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = stream.getReader();
  const onAbort = () => {
    void reader.cancel("aborted").catch(() => undefined);
  };
  signal?.addEventListener("abort", onAbort);
  if (signal?.aborted) onAbort();

  try {
    for (;;) {
      if (signal?.aborted) break;
      const result = await reader.read();
      if (result.done) break;
      onChunk(result.value);
    }
  } catch (error) {
    if (!isAbortError(error) && !signal?.aborted) throw error;
  } finally {
    signal?.removeEventListener("abort", onAbort);
    try {
      reader.releaseLock();
    } catch {
      // Lock may already be released after cancel.
    }
  }
}

const enum ControlChars {
  NewLine = 10,
  CarriageReturn = 13,
  Space = 32,
  Colon = 58,
}

function getLines(
  onLine: (line: Uint8Array, fieldLength: number) => void,
): (arr: Uint8Array) => void {
  let buffer: Uint8Array | undefined;
  let position = 0;
  let fieldLength = -1;
  let discardTrailingNewline = false;

  return function onChunk(arr: Uint8Array) {
    if (buffer === undefined) {
      buffer = arr;
      position = 0;
      fieldLength = -1;
    } else {
      buffer = concat(buffer, arr);
    }

    const bufLength = buffer.length;
    let lineStart = 0;
    while (position < bufLength) {
      if (discardTrailingNewline) {
        if (buffer[position] === ControlChars.NewLine) {
          lineStart = ++position;
        }
        discardTrailingNewline = false;
      }

      let lineEnd = -1;
      for (; position < bufLength && lineEnd === -1; ++position) {
        switch (buffer[position]) {
          case ControlChars.Colon:
            if (fieldLength === -1) {
              fieldLength = position - lineStart;
            }
            break;
          case ControlChars.CarriageReturn:
            discardTrailingNewline = true;
          // falls through
          case ControlChars.NewLine:
            lineEnd = position;
            break;
        }
      }

      if (lineEnd === -1) {
        break;
      }

      onLine(buffer.subarray(lineStart, lineEnd), fieldLength);
      lineStart = position;
      fieldLength = -1;
    }

    if (lineStart === bufLength) {
      buffer = undefined;
    } else if (lineStart !== 0) {
      buffer = buffer.subarray(lineStart);
      position -= lineStart;
    }
  };
}

function getMessages(
  onId: (id: string) => void,
  onRetry: (retry: number) => void,
  onMessage?: (msg: EventSourceMessage) => void,
): (line: Uint8Array, fieldLength: number) => void {
  let message = newMessage();
  const decoder = new TextDecoder();

  return function onLine(line: Uint8Array, fieldLength: number) {
    if (line.length === 0) {
      onMessage?.(message);
      message = newMessage();
      return;
    }

    if (fieldLength > 0) {
      const field = decoder.decode(line.subarray(0, fieldLength));
      const valueOffset =
        fieldLength + (line[fieldLength + 1] === ControlChars.Space ? 2 : 1);
      const value = decoder.decode(line.subarray(valueOffset));

      switch (field) {
        case "data":
          message.data = message.data ? `${message.data}\n${value}` : value;
          break;
        case "event":
          message.event = value;
          break;
        case "id":
          message.id = value;
          onId(value);
          break;
        case "retry": {
          const retry = Number.parseInt(value, 10);
          if (!Number.isNaN(retry)) {
            message.retry = retry;
            onRetry(retry);
          }
          break;
        }
      }
    }
  };
}

function concat(a: Uint8Array, b: Uint8Array): Uint8Array {
  const res = new Uint8Array(a.length + b.length);
  res.set(a);
  res.set(b, a.length);
  return res;
}

function newMessage(): EventSourceMessage {
  return {
    data: "",
    event: "",
    id: "",
    retry: undefined,
  };
}

/*
 * --- End vendored parsing core ---
 */

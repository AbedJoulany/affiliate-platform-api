import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  computeReconnectDelayMs,
  createQueueEventStream,
  getQueueStreamUrl,
} from "./sse-client";
import {
  QUEUE_EVENT_NAMES,
  type QueueEventEnvelope,
  type QueueEventEnvelopeBase,
} from "../types/events";

const encoder = new TextEncoder();

function streamFromChunks(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(chunk);
      }
      controller.close();
    },
  });
}

function streamFromTextChunks(parts: string[]): ReadableStream<Uint8Array> {
  return streamFromChunks(parts.map((part) => encoder.encode(part)));
}

function sampleEnvelope(
  overrides: Partial<QueueEventEnvelopeBase> = {},
): QueueEventEnvelope {
  return {
    event: QUEUE_EVENT_NAMES.STATUS_CHANGED,
    version: 1,
    id: "01HXEVENT000000000000000001",
    occurred_at: "2026-08-08T10:00:00.000Z",
    workspace_id: null,
    queue_id: "11111111-1111-1111-1111-111111111111",
    data: {
      queue_id: "11111111-1111-1111-1111-111111111111",
      status: "published",
      previous_status: "queued",
      scheduled_at: null,
      published_at: "2026-08-08T10:00:00.000Z",
    },
    ...overrides,
  } as QueueEventEnvelope;
}

function formatSseFrame(envelope: QueueEventEnvelope): string {
  return (
    `event: ${envelope.event}\n` +
    `id: ${envelope.id}\n` +
    `data: ${JSON.stringify(envelope)}\n` +
    `\n`
  );
}

function mockOk(body: ReadableStream<Uint8Array>): Response {
  return { ok: true, status: 200, body } as Response;
}

function mockStatus(status: number): Response {
  return { ok: false, status, body: null } as Response;
}

async function connectAndCollect(
  bodyFactory: () => ReadableStream<Uint8Array>,
  onMessage: (event: QueueEventEnvelope) => void,
): Promise<void> {
  const controller = new AbortController();
  const onOpen = vi.fn();
  const done = createQueueEventStream({
    token: "test-token",
    signal: controller.signal,
    onMessage,
    onOpen,
    fetchImpl: async () => mockOk(bodyFactory()),
    initialBackoffMs: 50,
    maxBackoffMs: 50,
    random: () => 0,
  });
  await vi.waitFor(() => expect(onOpen).toHaveBeenCalled());
  await vi.waitFor(() => expect(onMessage).toHaveBeenCalled());
  controller.abort();
  await done;
}

describe("computeReconnectDelayMs", () => {
  it("uses exponential steps capped at max with zero jitter", () => {
    const random = () => 0;
    expect(computeReconnectDelayMs(0, 1000, 30_000, random)).toBe(1000);
    expect(computeReconnectDelayMs(1, 1000, 30_000, random)).toBe(2000);
    expect(computeReconnectDelayMs(2, 1000, 30_000, random)).toBe(4000);
    expect(computeReconnectDelayMs(4, 1000, 30_000, random)).toBe(16_000);
    expect(computeReconnectDelayMs(10, 1000, 30_000, random)).toBe(30_000);
  });

  it("adds bounded jitter", () => {
    const random = () => 1;
    expect(computeReconnectDelayMs(0, 1000, 30_000, random)).toBe(2000);
  });
});

describe("getQueueStreamUrl", () => {
  it("appends /queues/stream to the API base", () => {
    expect(getQueueStreamUrl()).toMatch(/\/queues\/stream$/);
  });
});

describe("createQueueEventStream — parsing", () => {
  it("parses a single event frame", async () => {
    const envelope = sampleEnvelope();
    const onMessage = vi.fn();
    await connectAndCollect(
      () => streamFromTextChunks([formatSseFrame(envelope)]),
      onMessage,
    );
    expect(onMessage.mock.calls[0][0]).toMatchObject({
      event: QUEUE_EVENT_NAMES.STATUS_CHANGED,
      id: envelope.id,
      queue_id: envelope.queue_id,
    });
  });

  it("joins multi-line data fields into one JSON payload", async () => {
    const onMessage = vi.fn();
    const jsonSplit =
      "id: multi-3\n" +
      'data: {"event":"queue.deleted","version":1,"id":"multi-3",\n' +
      'data: "occurred_at":"2026-08-08T10:00:00.000Z","workspace_id":null,\n' +
      'data: "queue_id":"q1","data":{"queue_id":"q1"}}\n' +
      "\n";
    await connectAndCollect(() => streamFromTextChunks([jsonSplit]), onMessage);
    expect(onMessage.mock.calls[0][0]).toMatchObject({
      event: QUEUE_EVENT_NAMES.DELETED,
      id: "multi-3",
      queue_id: "q1",
    });
  });

  it("ignores heartbeat comment frames", async () => {
    const envelope = sampleEnvelope({ id: "after-hb" });
    const onMessage = vi.fn();
    const body = `: heartbeat\n\n${formatSseFrame(envelope)}`;
    await connectAndCollect(() => streamFromTextChunks([body]), onMessage);
    expect(onMessage.mock.calls[0][0].id).toBe("after-hb");
  });

  it("handles frames split across chunk boundaries", async () => {
    const envelope = sampleEnvelope({ id: "chunked-1" });
    const frame = formatSseFrame(envelope);
    const mid = Math.floor(frame.length / 2);
    const onMessage = vi.fn();
    await connectAndCollect(
      () => streamFromTextChunks([frame.slice(0, mid), frame.slice(mid)]),
      onMessage,
    );
    expect(onMessage.mock.calls[0][0].id).toBe("chunked-1");
  });

  it("handles UTF-8 characters split across chunks", async () => {
    const arabicTitle = "منتج تجريبي";
    const envelope = sampleEnvelope({
      id: "utf8-1",
      data: { queue_id: "q1", note: arabicTitle },
    });
    const frame = formatSseFrame(envelope);
    const bytes = encoder.encode(frame);
    let splitAt = Math.floor(bytes.length / 2);
    while (splitAt > 0 && (bytes[splitAt] & 0xc0) === 0x80) {
      splitAt -= 1;
    }
    const onMessage = vi.fn();
    await connectAndCollect(
      () => streamFromChunks([bytes.slice(0, splitAt), bytes.slice(splitAt)]),
      onMessage,
    );
    expect(onMessage.mock.calls[0][0].data).toMatchObject({
      note: arabicTitle,
    });
  });
});

describe("createQueueEventStream — client behavior", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("sends Authorization and Last-Event-ID headers", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(async (_url: string, init?: RequestInit) => {
      controller.abort();
      return mockOk(streamFromTextChunks([]));
    });

    await createQueueEventStream({
      token: "jwt-abc",
      signal: controller.signal,
      lastEventId: "prev-event-id",
      onMessage: vi.fn(),
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });

    expect(fetchImpl).toHaveBeenCalled();
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer jwt-abc");
    expect(headers["Last-Event-ID"]).toBe("prev-event-id");
    expect(headers.Accept).toBe("text/event-stream");
  });

  it("forwards last event id from a prior message on reconnect", async () => {
    const controller = new AbortController();
    const envelope = sampleEnvelope({ id: "cursor-42" });
    let call = 0;

    const fetchImpl = vi.fn(async () => {
      call += 1;
      if (call === 1) {
        return mockOk(streamFromTextChunks([formatSseFrame(envelope)]));
      }
      const [, init] = fetchImpl.mock.calls[call - 1] as unknown as [
        string,
        RequestInit,
      ];
      const headers = init.headers as Record<string, string>;
      expect(headers["Last-Event-ID"]).toBe("cursor-42");
      controller.abort();
      return mockOk(streamFromTextChunks([]));
    });

    const done = createQueueEventStream({
      token: "jwt-abc",
      signal: controller.signal,
      onMessage: vi.fn(),
      fetchImpl: fetchImpl as unknown as typeof fetch,
      random: () => 0,
      initialBackoffMs: 1000,
      maxBackoffMs: 1000,
    });

    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(1000);
    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(2));
    await done;
  });

  it("reconnects after a network failure with backoff", async () => {
    const controller = new AbortController();
    let call = 0;
    const onReconnect = vi.fn();

    const fetchImpl = vi.fn(async () => {
      call += 1;
      if (call === 1) {
        throw new TypeError("network down");
      }
      controller.abort();
      return mockOk(streamFromTextChunks([]));
    });

    const done = createQueueEventStream({
      token: "jwt-abc",
      signal: controller.signal,
      onMessage: vi.fn(),
      onReconnect,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      random: () => 0,
      initialBackoffMs: 1000,
      maxBackoffMs: 30_000,
    });

    await vi.waitFor(() => expect(onReconnect).toHaveBeenCalledWith(1, 1000));
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(2));
    await done;
  });

  it("stops reconnecting on auth errors", async () => {
    const controller = new AbortController();
    const onError = vi.fn();
    const fetchImpl = vi.fn(async () => mockStatus(401));

    await createQueueEventStream({
      token: "expired",
      signal: controller.signal,
      onMessage: vi.fn(),
      onError,
      fetchImpl: fetchImpl as unknown as typeof fetch,
      random: () => 0,
      initialBackoffMs: 1000,
      maxBackoffMs: 1000,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "auth", status: 401, fatal: true }),
    );
  });

  it("aborts cleanly without leaving a dangling loop", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(async () =>
      mockOk(
        new ReadableStream({
          start() {
            /* held open until abort cancels the reader */
          },
        }),
      ),
    );

    const done = createQueueEventStream({
      token: "jwt-abc",
      signal: controller.signal,
      onMessage: vi.fn(),
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });

    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));
    controller.abort();
    await expect(done).resolves.toBeUndefined();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});

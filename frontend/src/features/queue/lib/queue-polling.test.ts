import { describe, expect, it } from "vitest";
import type { Query } from "@tanstack/react-query";
import {
  QUEUE_POLL_FALLBACK_MAX_MS,
  QUEUE_POLL_FALLBACK_MIN_MS,
  computeQueuePollIntervalMs,
  createQueuePollIntervalSelector,
} from "./queue-polling";

function fakeQuery(
  overrides: Partial<Query["state"]> & {
    data?: unknown;
    dataUpdateCount?: number;
    fetchStatus?: Query["state"]["fetchStatus"];
  } = {},
): Query {
  const {
    data,
    dataUpdateCount = 0,
    fetchStatus = "idle",
    ...rest
  } = overrides;
  return {
    state: {
      data,
      dataUpdateCount,
      fetchStatus,
      ...rest,
    },
  } as Query;
}

describe("queue polling fallback helpers", () => {
  it("computes 5s → 30s backoff cadence", () => {
    expect(computeQueuePollIntervalMs(0)).toBe(QUEUE_POLL_FALLBACK_MIN_MS);
    expect(computeQueuePollIntervalMs(1)).toBe(10_000);
    expect(computeQueuePollIntervalMs(2)).toBe(20_000);
    expect(computeQueuePollIntervalMs(3)).toBe(QUEUE_POLL_FALLBACK_MAX_MS);
    expect(computeQueuePollIntervalMs(8)).toBe(QUEUE_POLL_FALLBACK_MAX_MS);
  });

  it("starts at 5s and backs off only after unchanged fetches", () => {
    const select = createQueuePollIntervalSelector();
    const payload = { items: [], total: 0 };

    expect(select(fakeQuery({ data: payload, dataUpdateCount: 1 }))).toBe(
      QUEUE_POLL_FALLBACK_MIN_MS,
    );

    expect(
      select(fakeQuery({ data: payload, dataUpdateCount: 2, fetchStatus: "idle" })),
    ).toBe(10_000);

    expect(
      select(fakeQuery({ data: payload, dataUpdateCount: 3, fetchStatus: "idle" })),
    ).toBe(20_000);

    const nextPayload = { items: [{ id: "1" }], total: 1 };
    expect(
      select(
        fakeQuery({ data: nextPayload, dataUpdateCount: 4, fetchStatus: "idle" }),
      ),
    ).toBe(QUEUE_POLL_FALLBACK_MIN_MS);
  });
});

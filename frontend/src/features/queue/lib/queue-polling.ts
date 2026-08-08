import type { Query } from "@tanstack/react-query";

/** Design/roadmap fallback cadence: start at 5s, back off to 30s when unchanged. */
export const QUEUE_POLL_FALLBACK_MIN_MS = 5_000;
export const QUEUE_POLL_FALLBACK_MAX_MS = 30_000;

/**
 * Map consecutive unchanged poll results to the next refetch interval.
 * streak 0 → 5s, 1 → 10s, 2 → 20s, 3+ → 30s (capped).
 */
export function computeQueuePollIntervalMs(consecutiveUnchanged: number): number {
  const exp =
    QUEUE_POLL_FALLBACK_MIN_MS * 2 ** Math.max(0, consecutiveUnchanged);
  return Math.min(exp, QUEUE_POLL_FALLBACK_MAX_MS);
}

type PollIntervalQuery = Pick<Query, "state">;

/**
 * TanStack Query `refetchInterval` selector for SSE fallback polling.
 * Uses referential equality (structural sharing) to detect unchanged data.
 * One selector instance per active polling session — do not share across hooks.
 */
export function createQueuePollIntervalSelector(): (
  query: PollIntervalQuery,
) => number | false {
  let lastData: unknown = undefined;
  let lastDataUpdateCount = -1;
  let unchangedStreak = 0;

  return (query: PollIntervalQuery): number | false => {
    const { data, dataUpdateCount, fetchStatus } = query.state;

    if (fetchStatus === "fetching") {
      return computeQueuePollIntervalMs(unchangedStreak);
    }

    if (dataUpdateCount !== lastDataUpdateCount) {
      if (lastDataUpdateCount >= 0 && Object.is(data, lastData)) {
        unchangedStreak += 1;
      } else if (lastDataUpdateCount >= 0) {
        unchangedStreak = 0;
      }
      lastData = data;
      lastDataUpdateCount = dataUpdateCount;
    }

    return computeQueuePollIntervalMs(unchangedStreak);
  };
}

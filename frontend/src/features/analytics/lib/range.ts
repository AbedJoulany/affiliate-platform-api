const DAY_MS = 24 * 60 * 60 * 1000;
export const DEFAULT_ANALYTICS_DAYS = 30;

function toUtcDateInput(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export function defaultAnalyticsRange(now = new Date()): {
  fromDate: string;
  toDate: string;
} {
  const to = new Date(now);
  const from = new Date(to.getTime() - DEFAULT_ANALYTICS_DAYS * DAY_MS);
  return { fromDate: toUtcDateInput(from), toDate: toUtcDateInput(to) };
}

export function rangeToQuery(fromDate: string, toDate: string): { from: string; to: string } {
  return {
    from: `${fromDate}T00:00:00.000Z`,
    to: `${toDate}T23:59:59.999Z`,
  };
}

export function formatRate(rate: number): string {
  return `${(rate * 100).toLocaleString("ar", { maximumFractionDigits: 1 })}%`;
}

export function formatRevenue(value: string | number): string {
  return Number(value).toLocaleString("ar", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

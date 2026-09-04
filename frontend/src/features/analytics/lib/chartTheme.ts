export function cssHslToken(token: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  return raw ? `hsl(${raw})` : fallback;
}

export function analyticsChartColors() {
  return {
    clicks: cssHslToken("--primary", "hsl(255 72% 58%)"),
    conversions: cssHslToken("--destructive", "hsl(0 72% 51%)"),
    axis: cssHslToken("--muted-foreground", "hsl(220 10% 42%)"),
    grid: cssHslToken("--border", "hsl(220 16% 88%)"),
    tooltipBg: cssHslToken("--surface", "hsl(0 0% 100%)"),
    tooltipFg: cssHslToken("--surface-foreground", "hsl(222 35% 12%)"),
  };
}

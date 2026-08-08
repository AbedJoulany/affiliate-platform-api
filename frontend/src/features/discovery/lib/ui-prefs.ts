import type { DiscoveryTableColumn, DiscoveryUiPrefs, TableDensity } from "../types/api";

export const DEFAULT_VISIBLE_COLUMNS: DiscoveryTableColumn[] = [
  "product",
  "price",
  "rating",
  "orders",
  "commission",
  "score",
  "status",
  "actions",
];

export const DEFAULT_UI_PREFS: DiscoveryUiPrefs = {
  density: "comfortable",
  visibleColumns: DEFAULT_VISIBLE_COLUMNS,
  resultSearch: "",
};

export function normalizeUiPrefs(prefs?: Partial<DiscoveryUiPrefs> | null): DiscoveryUiPrefs {
  const density: TableDensity =
    prefs?.density === "compact" || prefs?.density === "comfortable"
      ? prefs.density
      : DEFAULT_UI_PREFS.density;
  const visibleColumns =
    prefs?.visibleColumns?.length ? prefs.visibleColumns : DEFAULT_VISIBLE_COLUMNS;
  return {
    density,
    visibleColumns,
    resultSearch: prefs?.resultSearch ?? "",
  };
}

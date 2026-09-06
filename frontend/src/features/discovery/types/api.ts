import type { Product } from "@/features/products/types/api";

export type DiscoveryMode = "general" | "hot" | "deals" | "trending" | "category";
export type ProductSort =
  | "orders_desc"
  | "rating_desc"
  | "discount_desc"
  | "price_asc"
  | "price_desc"
  | "commission_desc"
  | "newest";

export type DiscoveryResultsView = "table" | "grid";
export type TableDensity = "comfortable" | "compact";

export type DiscoveryTableColumn =
  | "product"
  | "price"
  | "rating"
  | "orders"
  | "commission"
  | "score"
  | "status"
  | "actions";

export interface DiscoveryProduct {
  aliexpress_product_id: string;
  title: string;
  description: string | null;
  price: number;
  original_price: number | null;
  discount: number;
  rating: number;
  sales: number;
  reviews: number;
  image_url: string;
  gallery_images: string[];
  product_url: string;
  affiliate_url: string | null;
  category: string | null;
  store_name: string | null;
  currency: string;
  commission_rate: number | null;
  shipping_info: Record<string, unknown> | null;
  score: number;
  /** Reserved for future backend score_breakdown payloads. */
  score_breakdown?: ScoreBreakdown | null;
}

export interface ScoreFactor {
  key: "rating" | "sales" | "discount" | "reviews";
  label: string;
  weightPercent: number;
  inputValue: number;
  inputLabel: string;
}

export interface ScoreBreakdown {
  total: number;
  factors: ScoreFactor[];
  source: "backend" | "documented_weights";
}

export interface DiscoveryResponse {
  items: DiscoveryProduct[];
  total: number;
  skip: number;
  limit: number;
  page: number;
  total_pages: number;
  mode: DiscoveryMode;
  sort: ProductSort;
  persisted_count: number;
}

export interface DiscoveryParams {
  mode?: DiscoveryMode;
  keywords?: string;
  category_id?: string;
  min_rating?: number;
  min_orders?: number;
  min_price?: number;
  max_price?: number;
  min_discount?: number;
  shipping_country?: string;
  free_shipping?: boolean;
  choice_only?: boolean;
  /** UI-only until backend supports min commission. */
  min_commission?: number;
  /** Future-ready draft fields (not sent to API). */
  exclude_keywords?: string;
  max_orders?: number;
  max_discount?: number;
  max_commission?: number;
  store_rating?: number;
  sort?: ProductSort;
  page?: number;
  page_size?: number;
}

export interface DiscoveryUiPrefs {
  density: TableDensity;
  visibleColumns: DiscoveryTableColumn[];
  resultSearch: string;
}

export interface ProductImageSearchRequest {
  image_url?: string;
  image_base64?: string;
  page?: number;
  page_size?: number;
}

export interface ProductImageSearchKey {
  source: "url" | "upload";
  image_url?: string;
  fingerprint?: string;
  page: number;
}

export interface ProductImportResponse {
  product: Product;
  aliexpress_product_id: string;
  imported: boolean;
  image_count: number;
}

export interface ProductImportBatchResponse {
  imported: number;
  updated: number;
  failed: number;
  products: Product[];
}

export type DiscoveryRunStatus = "idle" | "running" | "success" | "error";

export interface DiscoverySessionSnapshot {
  draftParams: DiscoveryParams;
  committedParams: DiscoveryParams | null;
  lastResponse: DiscoveryResponse | null;
  lastRunAt: string | null;
  lastRunStatus: DiscoveryRunStatus;
  lastError: string | null;
  importedIds: string[];
  /** Extension point: Discovery Profiles / saved filters (future). */
  activeProfileId?: string | null;
  uiPrefs?: DiscoveryUiPrefs;
}

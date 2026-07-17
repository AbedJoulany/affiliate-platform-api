import type { Product } from "@/features/products/types/api";

export type DiscoveryMode = "general" | "hot" | "deals" | "trending" | "category";
export type ProductSort =
  | "orders_desc"
  | "price_asc"
  | "price_desc"
  | "commission_desc"
  | "discount_desc";

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
  sort?: ProductSort;
  page?: number;
  page_size?: number;
}

export interface ProductImportResponse {
  product: Product;
  aliexpress_product_id: string;
  imported: boolean;
  image_count: number;
}

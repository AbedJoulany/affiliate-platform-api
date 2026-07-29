export type ProductStatus = "draft" | "active" | "inactive" | "archived";

export interface Product {
  id: string;
  aliexpress_product_id: string | null;
  title: string;
  description: string | null;
  price: number;
  original_price: number | null;
  discount: number;
  rating: number;
  sales: number;
  reviews: number;
  image_url: string;
  gallery_images: string[] | null;
  product_url: string;
  affiliate_url: string | null;
  category: string | null;
  store_name: string | null;
  currency: string;
  commission_rate: number | null;
  shipping_info: Record<string, unknown> | null;
  score: number;
  status: ProductStatus;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  skip: number;
  limit: number;
}

export interface ProductListParams {
  title?: string;
  status?: ProductStatus;
  skip?: number;
  limit?: number;
}

export interface ProductUpdate {
  status?: ProductStatus;
}

export type ProductTableDensity = "comfortable" | "compact";

export type ProductTableColumn =
  | "product"
  | "price"
  | "rating"
  | "sales"
  | "score"
  | "status"
  | "actions";

export type ProductSort =
  | "newest"
  | "score_desc"
  | "sales_desc"
  | "rating_desc"
  | "price_asc"
  | "price_desc";

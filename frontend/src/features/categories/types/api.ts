export interface Category {
  category_id: number;
  category_name: string;
  parent_category_id: number;
  synced_at: string;
}

export interface CategoryListResponse {
  items: Category[];
  total: number;
  synced_at: string | null;
}

export interface ReadinessResponse {
  status: "ready" | "not_ready";
  checks: {
    database: { status: "up" | "down" };
    redis: { status: "up" | "down" };
  };
}

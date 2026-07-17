export interface DashboardOverview {
  products: {
    total: number;
    by_status: Record<"draft" | "active" | "inactive" | "archived", number>;
  };
  queue: {
    total: number;
    by_status: Record<"draft" | "queued" | "scheduled" | "published", number>;
  };
  channels: {
    total: number;
    active: number;
    inactive: number;
  };
  recent_activity: ReadonlyArray<{
    resource_type: "product" | "queue";
    resource_id: string;
    title: string;
    status: string;
    occurred_at: string;
  }>;
  system_status: {
    status: "operational";
    database: "up";
    generated_at: string;
  };
}

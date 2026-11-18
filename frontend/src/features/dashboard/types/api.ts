export interface DashboardOverview {
  products: {
    total: number;
    by_status: Record<"draft" | "active" | "inactive" | "archived", number>;
  };
  queue: {
    total: number;
    by_status: Record<
      "draft" | "queued" | "scheduled" | "published" | "failed",
      number
    >;
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
  reporting: {
    timezone: string;
    day_start_utc: string;
    day_end_utc: string;
    generated_at: string;
  };
  publishing: {
    published_today: number;
    failed_today: number;
    ambiguous_unresolved: number;
    by_provider: {
      telegram: {
        published: number;
        failed: number;
      };
      facebook: {
        published: number;
        failed: number;
      };
    };
  };
  attention_items: ReadonlyArray<{
    queue_id: string;
    title: string;
    provider: "telegram" | "facebook";
    issue: "failed" | "ambiguous";
    error_code: string | null;
    message: string | null;
    occurred_at: string;
  }>;
  destination_readiness: {
    telegram: {
      total: number;
      active: number;
      permission_granted: number;
    };
    facebook: {
      total: number;
      active: number;
      validated: number;
      publishing_permission_verified: boolean;
    };
  };
  automation: {
    status: "not_configured";
    last_run_at: string | null;
  };
}

export type AutomationProvider = "telegram" | "facebook";
export type AutomationExecutionState =
  | "disabled"
  | "configured_not_ready"
  | "configured_ready_not_active";
export type AutomationFrequency = "daily";
export type AutomationAiProvider = "openai" | "gemini";
export type AutomationLanguage = "ar" | "en" | "fr" | "de";
export type AutomationTone =
  | "professional"
  | "friendly"
  | "luxury"
  | "technical"
  | "urgent"
  | "minimal"
  | "persuasive"
  | "funny";
export type AutomationContentType =
  | "social"
  | "description"
  | "telegram"
  | "facebook"
  | "blog"
  | "email";
export type AutomationLength = "short" | "medium" | "long";

export interface AutomationDestination {
  provider: AutomationProvider;
  channel_id: string | null;
  page_id: string | null;
  label: string | null;
  active: boolean | null;
  ready: boolean;
  status:
    | "ready"
    | "missing"
    | "inactive"
    | "permission_missing"
    | "not_validated"
    | "unknown";
}

export interface AutomationDiscovery {
  keywords: string | null;
  min_price: string | number | null;
  max_price: string | number | null;
  min_rating: string | number | null;
  min_orders: number | null;
  min_discount: string | number | null;
  min_commission: string | number | null;
  max_commission: string | number | null;
  products_per_run: number;
}

export interface AutomationSchedule {
  frequency: AutomationFrequency;
  preferred_time_local: string;
  timezone: string;
  posts_per_day: number;
}

export interface AutomationContent {
  ai_provider: AutomationAiProvider | null;
  language: AutomationLanguage | null;
  tone: AutomationTone | null;
  content_type: AutomationContentType | null;
  length: AutomationLength | null;
}

export interface AutomationPolicy {
  id: string | null;
  workspace_id: string;
  revision: number;
  enabled: boolean;
  configuration_ready: boolean;
  execution_available: false;
  execution_state: AutomationExecutionState;
  destination: AutomationDestination | null;
  discovery: AutomationDiscovery;
  schedule: AutomationSchedule;
  content: AutomationContent;
  warnings: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface AutomationDestinationPatch {
  provider: AutomationProvider;
  channel_id?: string;
  page_id?: string;
}

export interface AutomationDiscoveryPatch {
  keywords?: string | null;
  min_price?: string | null;
  max_price?: string | null;
  min_rating?: string | null;
  min_orders?: number | null;
  min_discount?: string | null;
  min_commission?: string | null;
  max_commission?: string | null;
  products_per_run?: number;
}

export interface AutomationSchedulePatch {
  frequency?: AutomationFrequency;
  preferred_time_local?: string;
  posts_per_day?: number;
}

export interface AutomationContentPatch {
  ai_provider?: AutomationAiProvider | null;
  language?: AutomationLanguage | null;
  tone?: AutomationTone | null;
  content_type?: AutomationContentType | null;
  length?: AutomationLength | null;
}

export interface AutomationPolicyPatch {
  expected_revision: number;
  enabled?: boolean;
  destination?: AutomationDestinationPatch | null;
  discovery?: AutomationDiscoveryPatch;
  schedule?: AutomationSchedulePatch;
  content?: AutomationContentPatch;
}

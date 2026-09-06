export type UiLanguage = "ar" | "en";
export type AIProvider = "openai" | "gemini";
export type ContentType =
  | "social"
  | "description"
  | "telegram"
  | "facebook"
  | "blog"
  | "email";
export type ToneProfile =
  | "professional"
  | "friendly"
  | "luxury"
  | "technical"
  | "urgent"
  | "minimal"
  | "persuasive"
  | "funny";
export type ContentLanguage = "ar" | "en" | "fr" | "de";
export type ContentLength = "short" | "medium" | "long";
export type DiscoveryDefaultMode = "general" | "hot" | "deals" | "trending" | "category";

export type SettingsSection =
  | "general"
  | "aliexpress"
  | "ai"
  | "telegram"
  | "discovery"
  | "scheduling";

export interface ProviderConnectionStatus {
  aliexpress: boolean;
  telegram_bot: boolean;
  openai: boolean;
  gemini: boolean;
  image_search: boolean;
}

export interface WorkspaceSettings {
  workspace_id: string;
  can_edit: boolean;
  timezone: string;
  ui_language: UiLanguage;
  aliexpress_target_currency: string;
  aliexpress_ship_to_country: string;
  aliexpress_target_language: string;
  default_ai_provider: AIProvider;
  default_content_type: ContentType;
  default_tone: ToneProfile;
  default_content_language: ContentLanguage;
  default_content_length: ContentLength;
  discovery_default_mode: DiscoveryDefaultMode;
  discovery_page_size: number;
  default_telegram_channel_id: string | null;
  connections: ProviderConnectionStatus;
  created_at: string | null;
  updated_at: string | null;
}

export type WorkspaceSettingsPatch = Partial<{
  timezone: string;
  ui_language: UiLanguage;
  aliexpress_target_currency: string;
  aliexpress_ship_to_country: string;
  aliexpress_target_language: string;
  default_ai_provider: AIProvider;
  default_content_type: ContentType;
  default_tone: ToneProfile;
  default_content_language: ContentLanguage;
  default_content_length: ContentLength;
  discovery_default_mode: DiscoveryDefaultMode;
  discovery_page_size: number;
  default_telegram_channel_id: string | null;
}>;

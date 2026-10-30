export type BotPermissionStatus = "unknown" | "pending" | "granted" | "partial" | "denied";

export interface Channel {
  id: string;
  telegram_channel_id: string;
  title: string | null;
  username: string | null;
  bot_permission_status: BotPermissionStatus;
  can_post_messages: boolean;
  can_edit_messages: boolean;
  can_delete_messages: boolean;
  permissions_checked_at: string | null;
  permission_detail: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChannelListResponse {
  items: Channel[];
  total: number;
  skip: number;
  limit: number;
}

export interface ChannelCreate {
  telegram_channel_id: string;
  title?: string;
  is_active: boolean;
}

export type FacebookPageValidationStatus = "unknown" | "valid" | "invalid";

export interface FacebookPage {
  id: string;
  workspace_id: string;
  facebook_page_id: string;
  page_name: string;
  token_expires_at: string | null;
  is_active: boolean;
  validation_status: FacebookPageValidationStatus;
  last_validated_at: string | null;
  last_error: string | null;
  has_access_token: boolean;
  created_at: string;
  updated_at: string;
}

export interface FacebookPageListResponse {
  items: FacebookPage[];
  total: number;
  skip: number;
  limit: number;
}

export interface FacebookPageCreate {
  facebook_page_id: string;
  access_token: string;
  token_expires_at?: string;
}

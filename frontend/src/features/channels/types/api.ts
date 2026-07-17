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

export type UserRole = "admin" | "affiliate" | "advertiser";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  default_workspace_id: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  refresh_token: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

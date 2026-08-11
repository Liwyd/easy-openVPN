export type UserStatus = "active" | "limited" | "expired" | "disabled";

export interface User {
  id: number;
  username: string;
  admin_id: number;
  status: UserStatus;
  created_at: string;
  data_limit: number | null;
  data_used: number;
  data_limit_reset_strategy: string;
  expire_at: string | null;
  time_window_start: string | null;
  time_window_end: string | null;
  note: string | null;
  revoked: boolean;
  common_name: string | null;
}

export interface UsersQueryResult {
  users: User[];
  total: number;
}

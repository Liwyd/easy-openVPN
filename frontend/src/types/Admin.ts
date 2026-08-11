export interface Admin {
  id: number;
  username: string;
  is_sudo: boolean;
  disabled: boolean;
  created_at: string;
  data_limit: number | null;
  data_used: number;
  parent_admin_id: number | null;
  user_count: number;
  limitless_user_count: number;
}

export interface AdminsQueryResult {
  admins: Admin[];
  total: number;
}

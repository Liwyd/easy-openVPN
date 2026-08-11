import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import type { User, UsersQueryResult } from "../types/User";

export const USERS_PER_PAGE_KEY = "eovpanel_users_per_page";

export function useUsersQuery(params: {
  search: string;
  page: number;
  perPage: number;
}) {
  const offset = (params.page - 1) * params.perPage;
  return useQuery<UsersQueryResult>({
    queryKey: ["users", params.search, offset, params.perPage],
    queryFn: async () => {
      const q: Record<string, string | number> = {
        limit: params.perPage,
        offset,
      };
      if (params.search.trim()) q.username = params.search.trim();
      const res = await api.get("/users", { params: q });
      const total = Number(res.headers["x-total-count"] ?? res.data.length);
      return { users: res.data as User[], total };
    },
  });
}

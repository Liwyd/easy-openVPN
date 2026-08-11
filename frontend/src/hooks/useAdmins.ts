import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import type { Admin, AdminsQueryResult } from "../types/Admin";

export const ADMINS_PER_PAGE_KEY = "eovpanel_admins_per_page";

export function useAdminsQuery(params: {
  search: string;
  page: number;
  perPage: number;
}) {
  const offset = (params.page - 1) * params.perPage;
  return useQuery<AdminsQueryResult>({
    queryKey: ["admins", params.search, offset, params.perPage],
    queryFn: async () => {
      const q: Record<string, string | number> = {
        limit: params.perPage,
        offset,
      };
      if (params.search.trim()) q.username = params.search.trim();
      const res = await api.get("/admins", { params: q });
      const total = Number(res.headers["x-total-count"] ?? res.data.length);
      return { admins: res.data as Admin[], total };
    },
  });
}

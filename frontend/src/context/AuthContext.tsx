import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import api, { setTokens, clearTokens, getAccessToken } from "../lib/api";

interface Admin {
  id: number;
  username: string;
  is_sudo: boolean;
  disabled: boolean;
  created_at: string;
  data_limit: number | null;
  data_used: number;
  parent_admin_id: number | null;
}

interface AuthState {
  admin: Admin | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<Admin | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async () => {
    try {
      const { data } = await api.get<Admin>("/admin/me");
      setAdmin(data);
      return true;
    } catch {
      setAdmin(null);
      return false;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (getAccessToken()) {
        const ok = await fetchProfile();
        if (!cancelled && !ok) clearTokens();
      }
      if (!cancelled) setLoading(false);
    }
    init();
    return () => {
      cancelled = true;
    };
  }, [fetchProfile]);

  const login = useCallback(
    async (username: string, password: string) => {
      const { data } = await api.post("/admin/token", { username, password });
      setTokens(data.access_token, data.refresh_token);
      await fetchProfile();
    },
    [fetchProfile],
  );

  const logout = useCallback(() => {
    clearTokens();
    setAdmin(null);
  }, []);

  return (
    <AuthContext.Provider value={{ admin, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

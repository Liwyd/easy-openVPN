import axios from "axios";
import { API_BASE, LOGIN_PATH } from "./base";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

const TOKEN_KEY = "eovpanel_access_token";
const REFRESH_KEY = "eovpanel_refresh_token";

let accessToken: string | null = localStorage.getItem(TOKEN_KEY);
let refreshToken: string | null = localStorage.getItem(REFRESH_KEY);
let isRefreshing = false;
let pendingQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

export function setTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function getAccessToken(): string | null {
  return accessToken;
}

function processQueue(err: unknown, token: string | null) {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (err || !token) reject(err);
    else resolve(token);
  });
  pendingQueue = [];
}

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    if (err.response?.status !== 401 || original._retry) {
      return Promise.reject(err);
    }

    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then((token) => {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      });
    }

    original._retry = true;
    isRefreshing = true;

    if (!refreshToken) {
      isRefreshing = false;
      clearTokens();
      window.location.href = LOGIN_PATH;
      return Promise.reject(err);
    }

    try {
      const { data } = await axios.post(`${API_BASE}/admin/refresh`, {
        refresh_token: refreshToken,
      });
      const newAccess: string = data.access_token;
      const newRefresh: string = data.refresh_token;
      setTokens(newAccess, newRefresh);
      processQueue(null, newAccess);
      original.headers.Authorization = `Bearer ${newAccess}`;
      return api(original);
    } catch (refreshErr) {
      processQueue(refreshErr, null);
      clearTokens();
      window.location.href = LOGIN_PATH;
      return Promise.reject(refreshErr);
    } finally {
      isRefreshing = false;
    }
  },
);

export default api;

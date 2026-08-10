/**
 * Runtime base path for the panel (e.g. "/dashboard").
 *
 * Injected into index.html by nginx only when a base path is configured at
 * install time (see frontend/entrypoint.sh). Base-path deployments serve the
 * whole panel — SPA routes, /api, and /sub — under this prefix to hide it
 * from internet scanners. Empty means the panel is served at the root.
 */
declare global {
  interface Window {
    __APP_BASE_PATH__?: string;
  }
}

const raw = window.__APP_BASE_PATH__ ?? "";

/** Normalized base path: leading slash, no trailing slash, no "//". */
export const BASE_PATH = raw
  .trim()
  .replace(/\/+/g, "/")
  .replace(/^([^/].*)$/, "/$1")
  .replace(/\/$/, "");

/** Full API prefix, e.g. "/dashboard/api" (or "/api" at the root). */
export const API_BASE = BASE_PATH ? `${BASE_PATH}/api` : "/api";

/** Full path for the login page, e.g. "/dashboard/login". */
export const LOGIN_PATH = BASE_PATH ? `${BASE_PATH}/login` : "/login";
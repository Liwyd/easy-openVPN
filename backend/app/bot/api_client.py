"""API client for bot-to-panel communication.

The interactive Telegram bot needs to perform CRUD operations on users,
admins, nodes, and system settings.  Rather than importing SQLAlchemy
models directly (which would create thread-safety issues since the bot
runs in a separate thread), this client communicates with the FastAPI
panel via its HTTP API — the same API used by the web frontend.

Authentication: The bot logs in once at startup using configured admin
credentials and caches the JWT access token.  If a request returns 401,
it re-authenticates automatically.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.bot.config import get_api_base_url, get_bot_credentials

logger = logging.getLogger(__name__)

# Module-level singleton — lazily initialised on first use.
_client: _ApiClient | None = None


class _ApiClient:
    """Thin HTTP client wrapping the eovpanel FastAPI endpoints."""

    def __init__(self, base_url: str, username: str, password: str):
        self._base = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._token_expiry: float = 0
        self._http = httpx.Client(timeout=30)

    # ── Auth ──────────────────────────────────────────────────────────

    def _authenticate(self) -> None:
        """Obtain a fresh access token from the panel."""
        try:
            resp = self._http.post(
                f"{self._base}/api/admin/token",
                json={"username": self._username, "password": self._password},
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            # Expire 60s early to avoid edge-case 401s
            self._token_expiry = time.time() + 1740  # 29 min
            logger.info("Bot API authenticated as %s", self._username)
        except Exception:
            logger.error("Bot API authentication failed", exc_info=True)
            self._access_token = None
            self._token_expiry = 0

    def _ensure_auth(self) -> None:
        """Make sure we have a valid token."""
        if not self._access_token or time.time() >= self._token_expiry:
            self._authenticate()

    def _headers(self) -> dict[str, str]:
        self._ensure_auth()
        h = {"Content-Type": "application/json"}
        if self._access_token:
            h["Authorization"] = f"Bearer {self._access_token}"
        return h

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request, retrying once on 401."""
        url = f"{self._base}{path}"
        resp = self._http.request(method, url, headers=self._headers(), **kwargs)
        if resp.status_code == 401:
            self._authenticate()
            resp = self._http.request(method, url, headers=self._headers(), **kwargs)
        return resp

    # ── Users ─────────────────────────────────────────────────────────

    def list_users(
        self, limit: int = 50, offset: int = 0, username: str | None = None
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if username:
            params["username"] = username
        resp = self._request("GET", "/api/users", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_user(self, username: str) -> dict:
        resp = self._request("GET", f"/api/users/{username}")
        resp.raise_for_status()
        return resp.json()

    def create_user(self, data: dict) -> dict:
        resp = self._request("POST", "/api/users", json=data)
        resp.raise_for_status()
        return resp.json()

    def update_user(self, username: str, data: dict) -> dict:
        resp = self._request("PUT", f"/api/users/{username}", json=data)
        resp.raise_for_status()
        return resp.json()

    def delete_user(self, username: str) -> None:
        resp = self._request("DELETE", f"/api/users/{username}")
        resp.raise_for_status()

    def disable_user(self, username: str) -> dict:
        resp = self._request("POST", f"/api/users/{username}/disable")
        resp.raise_for_status()
        return resp.json()

    def enable_user(self, username: str) -> dict:
        resp = self._request("POST", f"/api/users/{username}/enable")
        resp.raise_for_status()
        return resp.json()

    def reset_usage(self, username: str) -> dict:
        resp = self._request("POST", f"/api/users/{username}/reset-usage")
        resp.raise_for_status()
        return resp.json()

    def revoke_subscription(self, username: str) -> dict:
        resp = self._request("POST", f"/api/users/{username}/subscription/revoke")
        resp.raise_for_status()
        return resp.json()

    def get_subscription_url(self, username: str) -> str:
        resp = self._request("GET", f"/api/users/{username}/subscription-url")
        resp.raise_for_status()
        return resp.json().get("subscription_url", "")

    def get_user_config(self, username: str) -> str:
        """Download the .ovpn file content for a user."""
        resp = self._request("GET", f"/api/users/{username}/config")
        resp.raise_for_status()
        return resp.text

    # ── Admins ────────────────────────────────────────────────────────

    def get_admins(self) -> list[dict]:
        resp = self._request("GET", "/api/admins")
        resp.raise_for_status()
        return resp.json()

    def get_admin(self, admin_id: int) -> dict:
        resp = self._request("GET", f"/api/admins/{admin_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Nodes ─────────────────────────────────────────────────────────

    def list_nodes(self) -> list[dict]:
        resp = self._request("GET", "/api/nodes")
        resp.raise_for_status()
        return resp.json()

    def get_node(self, node_id: int) -> dict:
        resp = self._request("GET", f"/api/nodes/{node_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Stats ─────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        resp = self._request("GET", "/api/stats/summary")
        resp.raise_for_status()
        return resp.json()

    def get_status_breakdown(self) -> dict:
        resp = self._request("GET", "/api/stats/status-breakdown")
        resp.raise_for_status()
        return resp.json()

    def get_system_metrics(self) -> dict:
        resp = self._request("GET", "/api/stats/system")
        resp.raise_for_status()
        return resp.json()

    def get_my_usage(self) -> dict:
        resp = self._request("GET", "/api/stats/me/usage")
        resp.raise_for_status()
        return resp.json()

    # ── Backup ────────────────────────────────────────────────────────

    def get_backup_config(self) -> dict:
        resp = self._request("GET", "/api/backup/config")
        resp.raise_for_status()
        return resp.json()

    def create_backup(self) -> dict:
        resp = self._request("POST", "/api/backup/create")
        resp.raise_for_status()
        return resp.json()

    def list_backups(self) -> list[dict]:
        resp = self._request("GET", "/api/backup/list")
        resp.raise_for_status()
        return resp.json()

    # ── Server Config ─────────────────────────────────────────────────

    def get_server_config(self) -> dict:
        resp = self._request("GET", "/api/settings/server-config")
        resp.raise_for_status()
        return resp.json()

    # ── Health ────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        try:
            resp = self._http.get(f"{self._base}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False


def get_client() -> _ApiClient:
    """Return the singleton API client, creating it on first call."""
    global _client
    if _client is None:
        base_url = get_api_base_url()
        username, password = get_bot_credentials()
        _client = _ApiClient(base_url, username, password)
    return _client


def init_client() -> _ApiClient:
    """Force re-initialization (e.g. after config change)."""
    global _client
    base_url = get_api_base_url()
    username, password = get_bot_credentials()
    _client = _ApiClient(base_url, username, password)
    return _client

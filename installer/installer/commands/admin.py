"""Admin command — list and inspect admins via the backend API."""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime

from installer.output import banner, bold, dim, fail, heading, info, ok, warn
from installer.utils import ENV_FILE, REPO_ENV, read_env


def _get_panel_url(env: dict[str, str]) -> str:
    port = env.get("PANEL_PORT", "8000")
    host = env.get("PUBLIC_HOST", "127.0.0.1")
    if port and port != "80":
        return f"http://{host}:{port}"
    return f"http://{host}"


def _get_token(base_url: str, username: str, password: str) -> str | None:
    """Authenticate and return an access token."""
    data = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/admin/token",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            return body.get("access_token")
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def _api_get(base_url: str, token: str, path: str) -> list | dict | None:
    """Make an authenticated GET request."""
    req = urllib.request.Request(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def _fmt_bytes(b: int | float) -> str:
    if b == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = min(len(units) - 1, int(__import__("math").log(b, 1024)) if b > 0 else 0)
    return f"{b / (1024 ** i):.2f} {units[i]}"


def _fmt_date(s: str) -> str:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M:%S")
    except (ValueError, AttributeError):
        return s or "—"


def _col(text: str, width: int, align: str = "left") -> str:
    text = str(text)
    if align == "right":
        return text.rjust(width)
    elif align == "center":
        return text.center(width)
    return text.ljust(width)


def cmd_admin(args) -> None:
    """Show admin list and details."""
    banner()

    env_path = REPO_ENV if REPO_ENV.exists() else ENV_FILE
    if not env_path.exists():
        fail("No .env file found. Is eovpanel installed?")
        sys.exit(1)

    env = read_env(env_path)
    base_url = _get_panel_url(env)

    username = env.get("SUDO_USERNAME", "admin")
    password = env.get("SUDO_PASSWORD", "")

    if not password:
        fail("No SUDO_PASSWORD found in .env. Cannot authenticate.")
        sys.exit(1)

    info(f"Connecting to {base_url}...")
    token = _get_token(base_url, username, password)
    if not token:
        fail("Authentication failed. Check SUDO_USERNAME/SUDO_PASSWORD in .env.")
        sys.exit(1)
    ok("Authenticated.")

    admins = _api_get(base_url, token, "/api/admins?limit=200")
    if admins is None:
        fail("Failed to fetch admin list from API.")
        sys.exit(1)

    if not admins:
        warn("No admins found.")
        return

    # Also fetch billing summary for debt info
    billing = _api_get(base_url, token, "/billing/summary")
    billing_map = {}
    if isinstance(billing, list):
        for b in billing:
            billing_map[b.get("admin_id")] = b

    # ── Table rendering ──────────────────────────────────────────────────
    heading(f"Admins ({len(admins)})")

    cols = [
        ("Username", 16, "left"),
        ("Usage", 12, "right"),
        ("Users", 8, "right"),
        ("Limitless", 10, "right"),
        ("Sudo", 5, "center"),
        ("Disabled", 8, "center"),
        ("Created", 22, "left"),
        ("$/User", 8, "right"),
        ("$/GB", 8, "right"),
        ("Debt", 12, "right"),
        ("Capacity", 14, "right"),
    ]

    # Header
    header = " ┃ ".join(_col(name, w, a) for name, w, a in cols)
    sep = " ┃ ".join("━" * w for _, w, _ in cols)
    top = "┏━" + "━┳━".join("━" * w for _, w, _ in cols) + "━┓"
    mid = "┡━" + "━╇━".join("━" * w for _, w, _ in cols) + "━┩"
    bot = "┗━" + "━┻━".join("━" * w for _, w, _ in cols) + "━┛"

    print(f"  {top}")
    print(f"  ┃ {bold(header)} ┃")
    print(f"  {mid}")

    for adm in admins:
        bid = adm.get("id")
        binfo = billing_map.get(bid, {})

        username_str = adm.get("username", "?")
        usage_str = _fmt_bytes(adm.get("data_used", 0))

        # Get user counts from billing summary if available, else show 0
        unlimited = binfo.get("unlimited_user_count", 0)
        volumed = binfo.get("volumed_user_count", 0)
        total_users = str(unlimited + volumed)
        limitless_str = str(unlimited)

        sudo_str = "✔" if adm.get("is_sudo") else "✖"
        disabled_str = "✔" if adm.get("disabled") else "✖"
        created_str = _fmt_date(adm.get("created_at", ""))

        price_user = binfo.get("price_per_user")
        price_gb = binfo.get("price_per_gb")
        debt = binfo.get("debt", 0) or adm.get("debt", 0) or 0

        pu_str = f"${price_user}" if price_user is not None else "—"
        pg_str = f"${price_gb}" if price_gb is not None else "—"
        debt_str = f"${debt:.2f}" if debt > 0 else "$0"

        dl = adm.get("data_limit")
        du = adm.get("data_used", 0)
        if dl is not None:
            cap_str = f"{_fmt_bytes(du)}/{_fmt_bytes(dl)}"
        else:
            cap_str = "Unlimited"

        row = [
            _col(username_str, 16),
            _col(usage_str, 12, "right"),
            _col(total_users, 8, "right"),
            _col(limitless_str, 10, "right"),
            _col(sudo_str, 5, "center"),
            _col(disabled_str, 8, "center"),
            _col(created_str, 22),
            _col(pu_str, 8, "right"),
            _col(pg_str, 8, "right"),
            _col(debt_str, 12, "right"),
            _col(cap_str, 14, "right"),
        ]
        print(f"  ┃ {' ┃ '.join(row)} ┃")

    print(f"  {bot}")

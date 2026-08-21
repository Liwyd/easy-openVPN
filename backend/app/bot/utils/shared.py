"""Shared text formatting utilities — mirrors Marzban's shared.py.

Status emojis, time-to-string conversion, and user info text generation
adapted for eovpanel's User model (OpenVPN, no proxies/inbounds).
"""

from __future__ import annotations

import re
from datetime import UTC, timezone
from datetime import datetime as dt

# Status emoji mapping — matches Marzban exactly
STATUSES = {
    "active": "✅",
    "expired": "🕰",
    "limited": "📵",
    "disabled": "❌",
}

SEP = "\u2796" * 10  # ➖➖➖➖➖➖➖➖➖


def time_to_string(time: dt) -> str:
    """Convert a datetime to a human-readable relative time string."""
    now = dt.now(UTC) if time.tzinfo else dt.now()
    if time.tzinfo is None:
        time = time.replace(tzinfo=UTC)
    if time < now:
        delta = now - time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if days > 0:
            return f"about <code>{days}</code> days ago"
        elif hours > 0:
            return f"about <code>{hours}</code> hours ago"
        elif minutes > 0:
            return f"about <code>{minutes}</code> minutes ago"
        else:
            return "just now"
    else:
        delta = time - now
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if days > 0:
            return f"in about <code>{days}</code> days"
        elif hours > 0:
            return f"in about <code>{hours}</code> hours"
        elif minutes > 0:
            return f"in about <code>{minutes}</code> minutes"
        else:
            return "very soon"


def fmt_bytes(n: int | None) -> str:
    """Human-readable byte size."""
    if n is None:
        return "Unlimited"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def get_user_info_text(user: dict) -> str:
    """Build the Marzban-style user info message from a UserResponse dict.

    Adapted for eovpanel: no proxies/inbounds, uses nodes instead,
    uses common_name instead of subscription_url for configs.
    """
    status = user.get("status", "active")
    status_emoji = STATUSES.get(status, "?")
    data_limit = user.get("data_limit")
    data_used = user.get("data_used", 0)
    expire_at = user.get("expire_at")

    data_limit_str = fmt_bytes(data_limit) if data_limit else "Unlimited"
    used_traffic_str = fmt_bytes(data_used) if data_used else "-"
    data_left_str = fmt_bytes(data_limit - data_used) if data_limit else "-"

    if expire_at:
        if isinstance(expire_at, str):
            try:
                expire_dt = dt.fromisoformat(expire_at.replace("Z", "+00:00"))
            except ValueError:
                expire_dt = None
        elif isinstance(expire_at, (int, float)):
            expire_dt = dt.fromtimestamp(expire_at, tz=UTC)
        else:
            expire_dt = expire_at
        expiry_date = expire_dt.strftime("%Y-%m-%d") if expire_dt else "Never"
        time_left = time_to_string(expire_dt) if expire_dt else "-"
    else:
        expiry_date = "Never"
        time_left = "-"

    online_at = "🟢 Online" if user.get("is_online") else "⚪ Offline"
    sub_updated = user.get("subscription_updated_at", "-")
    if sub_updated and sub_updated != "-":
        try:
            sub_dt = dt.fromisoformat(str(sub_updated).replace("Z", "+00:00"))
            sub_updated = time_to_string(sub_dt)
        except (ValueError, TypeError):
            pass

    note = user.get("note") or "empty"
    admin_username = user.get("admin_username", "-")
    subscription_url = user.get("subscription_url", "")

    text = f"""\
{status_emoji} <b>Status:</b> <code>{status.title()}</code>

🔤 <b>Username:</b> <code>{user['username']}</code>

🔋 <b>Data limit:</b> <code>{data_limit_str}</code>
📶 <b>Data Used:</b> <code>{used_traffic_str}</code> (<code>{data_left_str}</code> left)
📅 <b>Expiry Date:</b> <code>{expiry_date}</code> ({time_left})

{online_at}
🔄 <b>Subscription updated at:</b> {sub_updated}

📝 <b>Note:</b> <blockquote expandable>{note}</blockquote>
👨‍💻 <b>Admin:</b> <code>{admin_username}</code>"""

    if subscription_url:
        text += f"""
🚀 <b><a href="{subscription_url}">Subscription</a>:</b> <code>{subscription_url}</code>"""

    return text


def get_number_at_end(username: str):
    """Extract trailing digits from a username."""
    n = re.search(r"(\d+)$", username)
    if n:
        return n.group(1)

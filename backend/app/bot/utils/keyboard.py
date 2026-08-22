"""Inline keyboard builders — 1:1 clone of Marzban's BotKeyboard.

Every button label, callback_data pattern, and row layout matches
Marzban's original ``app/telegram/utils/keyboard.py`` exactly.
Adaptations for eovpanel (OpenVPN nodes instead of Xray inbounds)
are noted in comments.
"""

from __future__ import annotations

from datetime import datetime as dt
from itertools import islice

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def chunk_dict(data: dict, size: int = 2):
    it = iter(data)
    for _i in range(0, len(data), size):
        yield {k: data[k] for k in islice(it, size)}


def _fmt_bytes(n: int | None) -> str:
    """Human-readable byte size (Marzban-compatible)."""
    if n is None:
        return "Unlimited"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def _kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    """Build an InlineKeyboardMarkup from variable-length rows."""
    return InlineKeyboardMarkup([list(row) for row in rows])


class BotKeyboard:

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        return _kb(
            [
                InlineKeyboardButton(text="🔁 System Info", callback_data="system"),
                InlineKeyboardButton(text="♻️ Restart OpenVPN", callback_data="restart"),
            ],
            [
                InlineKeyboardButton(text="👥 Users", callback_data="users:1"),
                InlineKeyboardButton(text="✏️ Edit All Users", callback_data="edit_all"),
            ],
            [InlineKeyboardButton(text="➕ Create User", callback_data="add_user")],
            [InlineKeyboardButton(text="➕ Create Bulk User", callback_data="add_bulk_user")],
            [InlineKeyboardButton(text="📦 Backup", callback_data="backup")],
        )

    @staticmethod
    def edit_all_menu() -> InlineKeyboardMarkup:
        return _kb(
            [
                InlineKeyboardButton(text="🗑 Delete Expired", callback_data="delete_expired"),
                InlineKeyboardButton(text="🗑 Delete Limited", callback_data="delete_limited"),
            ],
            [
                InlineKeyboardButton(text="🔋 Data (➕|➖)", callback_data="add_data"),
                InlineKeyboardButton(text="📅 Time (➕|➖)", callback_data="add_time"),
            ],
            [
                InlineKeyboardButton(text="➕ Add Node", callback_data="node_add"),
                InlineKeyboardButton(text="➖ Remove Node", callback_data="node_remove"),
            ],
            [InlineKeyboardButton(text="🔙 Back", callback_data="cancel")],
        )

    @staticmethod
    def nodes_menu(action: str, nodes: list[dict]) -> InlineKeyboardMarkup:
        """Show available nodes for bulk add/remove."""
        rows = []
        for node in nodes:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=node["name"],
                        callback_data=f"confirm_{action}:{node['name']}",
                    )
                ]
            )
        rows.append([InlineKeyboardButton(text="🔙 Back", callback_data="cancel")])
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def random_username() -> InlineKeyboardMarkup:
        return _kb(
            [InlineKeyboardButton(text="🔡 Random Username", callback_data="random:")],
            [InlineKeyboardButton(text="🔙 Cancel", callback_data="cancel")],
        )

    @staticmethod
    def user_menu(user_info: dict, with_back: bool = True, page: int = 1) -> InlineKeyboardMarkup:
        rows = [
            [
                InlineKeyboardButton(
                    text="❌ Disable" if user_info["status"] == "active" else "✅ Activate",
                    callback_data=(
                        f"{'suspend' if user_info['status'] == 'active' else 'activate'}"
                        f":{user_info['username']}"
                    ),
                ),
                InlineKeyboardButton(
                    text="🗑 Delete",
                    callback_data=f"delete:{user_info['username']}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Revoke Sub",
                    callback_data=f"revoke_sub:{user_info['username']}",
                ),
                InlineKeyboardButton(
                    text="✏️ Edit",
                    callback_data=f"edit:{user_info['username']}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📝 Edit Note",
                    callback_data=f"edit_note:{user_info['username']}",
                ),
                InlineKeyboardButton(
                    text="📡 Links",
                    callback_data=f"links:{user_info['username']}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Reset usage",
                    callback_data=f"reset_usage:{user_info['username']}",
                ),
                InlineKeyboardButton(
                    text="🔋 Charge",
                    callback_data=f"charge:{user_info['username']}",
                ),
            ],
        ]
        if with_back:
            rows.append(
                [InlineKeyboardButton(text="🔙 Back", callback_data=f"users:{page}")]
            )
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def user_status_select() -> InlineKeyboardMarkup:
        return _kb(
            [
                InlineKeyboardButton(text="🟢 active", callback_data="status:active"),
                InlineKeyboardButton(text="🟣 onhold", callback_data="status:onhold"),
            ],
            [InlineKeyboardButton(text="🔙 Back", callback_data="cancel")],
        )

    @staticmethod
    def show_links(username: str) -> InlineKeyboardMarkup:
        return _kb(
            [
                InlineKeyboardButton(
                    text="🖼 Config QRcode",
                    callback_data=f"genqr:configs:{username}",
                ),
                InlineKeyboardButton(
                    text="🚀 Sub QRcode",
                    callback_data=f"genqr:sub:{username}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data=f"user:{username}",
                )
            ],
        )

    @staticmethod
    def subscription_page(sub_url: str) -> InlineKeyboardMarkup:
        rows = []
        if sub_url and sub_url[:4] == "http":
            rows.append(
                [InlineKeyboardButton(text="🚀 Subscription Page", url=sub_url)]
            )
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def confirm_action(action: str, username: str | None = None) -> InlineKeyboardMarkup:
        return _kb(
            [
                InlineKeyboardButton(
                    text="Yes",
                    callback_data=f"confirm:{action}:{username}" if username else f"confirm:{action}",
                ),
                InlineKeyboardButton(text="No", callback_data="cancel"),
            ],
        )

    @staticmethod
    def charge_add_or_reset(username: str, data_limit: int | None, expire_at: str | None) -> InlineKeyboardMarkup:
        """Charge confirmation — add to current vs reset to defaults."""
        return _kb(
            [
                InlineKeyboardButton(
                    text="🔰 Add to current",
                    callback_data=f"confirm:charge_add:{username}",
                ),
                InlineKeyboardButton(
                    text="♻️ Reset",
                    callback_data=f"confirm:charge_reset:{username}",
                ),
            ],
            [InlineKeyboardButton(text="Cancel", callback_data=f"user:{username}")],
        )

    @staticmethod
    def inline_cancel_action(callback_data: str = "cancel") -> InlineKeyboardMarkup:
        return _kb(
            [InlineKeyboardButton(text="🔙 Cancel", callback_data=callback_data)]
        )

    @staticmethod
    def user_list(users: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
        rows = []
        if len(users) >= 2:
            users_list = [p for p in users]
            users_list = [users_list[i : i + 2] for i in range(0, len(users_list), 2)]
        else:
            users_list = [users]
        for user in users_list:
            row = []
            for p in user:
                status_map = {
                    "active": "✅",
                    "expired": "🕰",
                    "limited": "📵",
                    "disabled": "❌",
                }
                row.append(
                    InlineKeyboardButton(
                        text=f"{p['username']} ({status_map.get(p['status'], '?')})",
                        callback_data=f"user:{p['username']}:{page}",
                    )
                )
            rows.append(row)
        if total_pages > 1:
            if page > 1:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text="⬅️ Previous",
                            callback_data=f"users:{page - 1}",
                        )
                    ]
                )
            if page < total_pages:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text="➡️ Next",
                            callback_data=f"users:{page + 1}",
                        )
                    ]
                )
        rows.append([InlineKeyboardButton(text="🔙 Back", callback_data="cancel")])
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def select_nodes(
        selected_nodes: list[str],
        action: str,
        username: str | None = None,
        data_limit: int | None = None,
        expire_at: dt | None = None,
    ) -> InlineKeyboardMarkup:
        """Node selection keyboard for edit/create flows."""
        rows = []

        if action == "edit":
            rows.append(
                [InlineKeyboardButton(text="⚠️ Data Limit:", callback_data="help_edit")]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{_fmt_bytes(data_limit) if data_limit else 'Unlimited'}",
                        callback_data="help_edit",
                    ),
                    InlineKeyboardButton(
                        text="✏️ Edit", callback_data=f"edit_user:{username}:data"
                    ),
                ]
            )
            rows.append(
                [InlineKeyboardButton(text="📅 Expire Date:", callback_data="help_edit")]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{expire_at.strftime('%Y-%m-%d') if expire_at else 'Never'}",
                        callback_data="help_edit",
                    ),
                    InlineKeyboardButton(
                        text="✏️ Edit", callback_data=f"edit_user:{username}:expire"
                    ),
                ]
            )

        rows.append(
            [
                InlineKeyboardButton(
                    text="Done",
                    callback_data="confirm:edit_user" if action == "edit" else "confirm:add_user",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="Cancel",
                    callback_data=f"user:{username}" if action == "edit" else "cancel",
                )
            ]
        )
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def backup_menu(backup_config: dict | None = None) -> InlineKeyboardMarkup:
        """Backup submenu."""
        status = "✅ Enabled" if backup_config and backup_config.get("enabled") else "❌ Disabled"
        return _kb(
            [InlineKeyboardButton(text="📦 Send Backup Now", callback_data="backup_send")],
            [InlineKeyboardButton(text="📋 List Backups", callback_data="backup_list")],
            [
                InlineKeyboardButton(
                    text=f"⏰ Auto Backup: {status}",
                    callback_data="backup_toggle",
                )
            ],
            [InlineKeyboardButton(text="🔙 Back", callback_data="cancel")],
        )

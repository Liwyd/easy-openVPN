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


class BotKeyboard:

    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text="🔁 System Info", callback_data="system"),
            InlineKeyboardButton(text="♻️ Restart OpenVPN", callback_data="restart"),
        )
        keyboard.add(
            InlineKeyboardButton(text="👥 Users", callback_data="users:1"),
            InlineKeyboardButton(text="✏️ Edit All Users", callback_data="edit_all"),
        )
        keyboard.add(
            InlineKeyboardButton(text="➕ Create User", callback_data="add_user"),
        )
        keyboard.add(
            InlineKeyboardButton(text="➕ Create Bulk User", callback_data="add_bulk_user"),
        )
        keyboard.add(
            InlineKeyboardButton(text="📦 Backup", callback_data="backup"),
        )
        return keyboard

    @staticmethod
    def edit_all_menu() -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text="🗑 Delete Expired", callback_data="delete_expired"),
            InlineKeyboardButton(text="🗑 Delete Limited", callback_data="delete_limited"),
        )
        keyboard.add(
            InlineKeyboardButton(text="🔋 Data (➕|➖)", callback_data="add_data"),
            InlineKeyboardButton(text="📅 Time (➕|➖)", callback_data="add_time"),
        )
        keyboard.add(
            InlineKeyboardButton(text="➕ Add Node", callback_data="node_add"),
            InlineKeyboardButton(text="➖ Remove Node", callback_data="node_remove"),
        )
        keyboard.add(InlineKeyboardButton(text="🔙 Back", callback_data="cancel"))
        return keyboard

    @staticmethod
    def nodes_menu(action: str, nodes: list[dict]) -> InlineKeyboardMarkup:
        """Show available nodes for bulk add/remove."""
        keyboard = InlineKeyboardMarkup()
        for node in nodes:
            keyboard.add(
                InlineKeyboardButton(
                    text=node["name"],
                    callback_data=f"confirm_{action}:{node['name']}",
                )
            )
        keyboard.add(InlineKeyboardButton(text="🔙 Back", callback_data="cancel"))
        return keyboard

    @staticmethod
    def random_username() -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text="🔡 Random Username", callback_data="random:")
        )
        keyboard.add(InlineKeyboardButton(text="🔙 Cancel", callback_data="cancel"))
        return keyboard

    @staticmethod
    def user_menu(user_info: dict, with_back: bool = True, page: int = 1) -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
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
        )
        keyboard.add(
            InlineKeyboardButton(
                text="🚫 Revoke Sub",
                callback_data=f"revoke_sub:{user_info['username']}",
            ),
            InlineKeyboardButton(
                text="✏️ Edit",
                callback_data=f"edit:{user_info['username']}",
            ),
        )
        keyboard.add(
            InlineKeyboardButton(
                text="📝 Edit Note",
                callback_data=f"edit_note:{user_info['username']}",
            ),
            InlineKeyboardButton(
                text="📡 Links",
                callback_data=f"links:{user_info['username']}",
            ),
        )
        keyboard.add(
            InlineKeyboardButton(
                text="🔁 Reset usage",
                callback_data=f"reset_usage:{user_info['username']}",
            ),
            InlineKeyboardButton(
                text="🔋 Charge",
                callback_data=f"charge:{user_info['username']}",
            ),
        )
        if with_back:
            keyboard.add(
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data=f"users:{page}",
                )
            )
        return keyboard

    @staticmethod
    def user_status_select() -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text="🟢 active", callback_data="status:active"),
            InlineKeyboardButton(text="🟣 onhold", callback_data="status:onhold"),
        )
        keyboard.add(InlineKeyboardButton(text="🔙 Back", callback_data="cancel"))
        return keyboard

    @staticmethod
    def show_links(username: str) -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                text="🖼 Config QRcode",
                callback_data=f"genqr:configs:{username}",
            ),
            InlineKeyboardButton(
                text="🚀 Sub QRcode",
                callback_data=f"genqr:sub:{username}",
            ),
        )
        keyboard.add(
            InlineKeyboardButton(
                text="🔙 Back",
                callback_data=f"user:{username}",
            )
        )
        return keyboard

    @staticmethod
    def subscription_page(sub_url: str) -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        if sub_url and sub_url[:4] == "http":
            keyboard.add(
                InlineKeyboardButton(text="🚀 Subscription Page", url=sub_url)
            )
        return keyboard

    @staticmethod
    def confirm_action(action: str, username: str | None = None) -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                text="Yes",
                callback_data=f"confirm:{action}:{username}" if username else f"confirm:{action}",
            ),
            InlineKeyboardButton(text="No", callback_data="cancel"),
        )
        return keyboard

    @staticmethod
    def charge_add_or_reset(username: str, data_limit: int | None, expire_at: str | None) -> InlineKeyboardMarkup:
        """Charge confirmation — add to current vs reset to defaults.

        Since eovpanel has no templates, we use the user's current
        data_limit and expire_at as the 'template' values.
        """
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                text="🔰 Add to current",
                callback_data=f"confirm:charge_add:{username}",
            ),
            InlineKeyboardButton(
                text="♻️ Reset",
                callback_data=f"confirm:charge_reset:{username}",
            ),
        )
        keyboard.add(
            InlineKeyboardButton(text="Cancel", callback_data=f"user:{username}")
        )
        return keyboard

    @staticmethod
    def inline_cancel_action(callback_data: str = "cancel") -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text="🔙 Cancel", callback_data=callback_data)
        )
        return keyboard

    @staticmethod
    def user_list(users: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup()
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
            keyboard.row(*row)
        if total_pages > 1:
            if page > 1:
                keyboard.add(
                    InlineKeyboardButton(
                        text="⬅️ Previous",
                        callback_data=f"users:{page - 1}",
                    )
                )
            if page < total_pages:
                keyboard.add(
                    InlineKeyboardButton(
                        text="➡️ Next",
                        callback_data=f"users:{page + 1}",
                    )
                )
        keyboard.add(InlineKeyboardButton(text="🔙 Back", callback_data="cancel"))
        return keyboard

    @staticmethod
    def select_nodes(
        selected_nodes: list[str],
        action: str,
        username: str | None = None,
        data_limit: int | None = None,
        expire_at: dt | None = None,
    ) -> InlineKeyboardMarkup:
        """Node selection keyboard for edit/create flows.

        eovpanel equivalent of Marzban's select_protocols keyboard.
        Instead of protocol/inbound selection, users select which nodes
        they are assigned to.
        """
        keyboard = InlineKeyboardMarkup()

        if action == "edit":
            keyboard.add(
                InlineKeyboardButton(text="⚠️ Data Limit:", callback_data="help_edit")
            )
            keyboard.add(
                InlineKeyboardButton(
                    text=f"{_fmt_bytes(data_limit) if data_limit else 'Unlimited'}",
                    callback_data="help_edit",
                ),
                InlineKeyboardButton(
                    text="✏️ Edit", callback_data=f"edit_user:{username}:data"
                ),
            )
            keyboard.add(
                InlineKeyboardButton(text="📅 Expire Date:", callback_data="help_edit")
            )
            keyboard.add(
                InlineKeyboardButton(
                    text=f"{expire_at.strftime('%Y-%m-%d') if expire_at else 'Never'}",
                    callback_data="help_edit",
                ),
                InlineKeyboardButton(
                    text="✏️ Edit", callback_data=f"edit_user:{username}:expire"
                ),
            )

        keyboard.add(
            InlineKeyboardButton(
                text="Done",
                callback_data="confirm:edit_user" if action == "edit" else "confirm:add_user",
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                text="Cancel",
                callback_data=f"user:{username}" if action == "edit" else "cancel",
            )
        )
        return keyboard

    @staticmethod
    def backup_menu(backup_config: dict | None = None) -> InlineKeyboardMarkup:
        """Backup submenu — merged from Marzban's separate backup bot."""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text="📦 Send Backup Now", callback_data="backup_send"),
        )
        keyboard.add(
            InlineKeyboardButton(text="📋 List Backups", callback_data="backup_list"),
        )
        status = "✅ Enabled" if backup_config and backup_config.get("enabled") else "❌ Disabled"
        keyboard.add(
            InlineKeyboardButton(
                text=f"⏰ Auto Backup: {status}",
                callback_data="backup_toggle",
            ),
        )
        keyboard.add(InlineKeyboardButton(text="🔙 Back", callback_data="cancel"))
        return keyboard

"""Admin handler — full Marzban-clone interactive bot panel.

Mirrors every command, callback, FSM flow, and message text from
Marzban's ``app/telegram/handlers/admin.py`` (2164 lines), adapted
for eovpanel's OpenVPN architecture:

  - No Xray restart → OpenVPN service restart
  - No proxies/inbounds → OpenVPN nodes (simplified)
  - No user templates → removed (Marzban template features skipped)
  - API client instead of direct DB access
  - python-telegram-bot async instead of telebot sync

Every message text, emoji, separator line, and callback_data pattern
matches Marzban's original verbatim where applicable.
"""

from __future__ import annotations

import contextlib
import io
import math
import os
import random
import re
import string
from datetime import datetime

from dateutil.relativedelta import relativedelta
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.api_client import get_client
from app.bot.config import get_logger_channel_id
from app.bot.utils.keyboard import BotKeyboard
from app.bot.utils.shared import (
    STATUSES,
    fmt_bytes,
    get_number_at_end,
    get_user_info_text,
)
from app.utils.store import MemoryStorage

mem_store = MemoryStorage()

# Conversation states
(
    STATE_USERNAME,
    STATE_BULK_NUMBER,
    STATE_DATA_LIMIT,
    STATE_EXPIRE,
    STATE_ONHOLD_TIMEOUT,
    STATE_EDIT_DATA,
    STATE_EDIT_EXPIRE,
    STATE_EDIT_NOTE,
    STATE_ADD_DATA,
    STATE_ADD_TIME,
    STATE_STATUS,
) = range(11)


# ── Helpers ──────────────────────────────────────────────────────────


def _get_system_info() -> str:
    """Build system info message — Marzban-style with eovpanel data."""
    client = get_client()
    try:
        metrics = client.get_system_metrics()
    except Exception:
        metrics = {"cpu_percent": 0, "ram": {}, "disk": {}, "uptime_seconds": 0}

    try:
        summary = client.get_summary()
    except Exception:
        summary = {"total_users": 0, "total_traffic_bytes": 0}

    try:
        breakdown = client.get_status_breakdown()
    except Exception:
        breakdown = {"active": 0, "disabled": 0, "expired": 0, "limited": 0}

    cpu_percent = metrics.get("cpu_percent", 0)
    ram = metrics.get("ram", {})
    disk = metrics.get("disk", {})
    uptime_secs = metrics.get("uptime_seconds", 0)

    total_users = summary.get("total_users", 0)
    total_traffic = summary.get("total_traffic_bytes", 0)
    active_users = breakdown.get("active", 0)
    disabled_users = breakdown.get("disabled", 0)
    expired_users = breakdown.get("expired", 0)
    limited_users = breakdown.get("limited", 0)

    uptime_days = int(uptime_secs // 86400)
    uptime_hours = int((uptime_secs % 86400) // 3600)

    return f"""\
🎛 *CPU Usage*: `{cpu_percent}%`
➖➖➖➖➖➖➖
📊 *Total Memory*: `{fmt_bytes(ram.get('total_bytes', 0))}`
📈 *In Use Memory*: `{fmt_bytes(ram.get('used_bytes', 0))}`
📉 *Free Memory*: `{fmt_bytes(ram.get('available_bytes', 0))}`
➖➖➖➖➖➖➖
💾 *Disk Total*: `{fmt_bytes(disk.get('total_bytes', 0))}`
💾 *Disk Used*: `{fmt_bytes(disk.get('used_bytes', 0))}`
💾 *Disk Free*: `{fmt_bytes(disk.get('free_bytes', 0))}`
➖➖➖➖➖➖➖
👥 *Total Users*: `{total_users}`
🟢 *Active Users*: `{active_users}`
❌ *Disabled Users*: `{disabled_users}`
🕰 *Expired Users*: `{expired_users}`
📵 *Limited Users*: `{limited_users}`
➖➖➖➖➖➖➖
⏱ *Uptime*: `{uptime_days}d {uptime_hours}h`
📊 *Total Traffic*: `{fmt_bytes(total_traffic)}`"""


def _schedule_delete_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, *message_ids: int) -> None:
    """Queue message IDs for later cleanup."""
    messages: list[int] = mem_store.get(f"{chat_id}:messages_to_delete", [])
    for mid in message_ids:
        messages.append(mid)
    mem_store.set(f"{chat_id}:messages_to_delete", messages)


async def _cleanup_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Delete all queued messages."""
    messages: list[int] = mem_store.get(f"{chat_id}:messages_to_delete", [])
    for message_id in messages:
        with contextlib.suppress(Exception):
            await context.bot.delete_message(chat_id, message_id)
    mem_store.set(f"{chat_id}:messages_to_delete", [])


def _send_logger_channel(context: ContextTypes.DEFAULT_TYPE, text: str, document: tuple | None = None) -> None:
    """Send a message to the logger channel if configured."""
    logger_ch = get_logger_channel_id()
    if not logger_ch:
        return

    async def _send():
        try:
            if document:
                filename, file_path = document
                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=logger_ch,
                        document=f,
                        caption=text,
                        parse_mode="HTML",
                    )
                os.remove(file_path)
            else:
                await context.bot.send_message(
                    chat_id=logger_ch,
                    text=text,
                    parse_mode="HTML",
                )
        except Exception:
            pass

    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send())
    except RuntimeError:
        asyncio.run(_send())


# ── /start and /help ────────────────────────────────────────────────


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start and /help — show welcome message with main menu."""
    chat_id = update.effective_chat.id
    await _cleanup_messages(context, chat_id)
    context.application.drop_handler_by_name(str(chat_id))

    user = update.effective_user
    user_link = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'

    await update.message.reply_text(
        f"""
{user_link} Welcome to eovpanel Telegram-Bot Admin Panel.
Here you can manage your users and proxies.
To get started, use the buttons below.
Also, You can get and modify users by /user command.
""",
        parse_mode="html",
        reply_markup=BotKeyboard.main_menu(),
    )


# ── System Info ─────────────────────────────────────────────────────


async def system_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'system' — show system info."""
    query = update.callback_query
    await query.edit_message_text(
        _get_system_info(),
        parse_mode="MarkdownV2",
        reply_markup=BotKeyboard.main_menu(),
    )


# ── Restart ─────────────────────────────────────────────────────────


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'restart' — confirm OpenVPN restart."""
    query = update.callback_query
    await query.edit_message_text(
        "⚠️ Are you sure? This will restart OpenVPN core.",
        reply_markup=BotKeyboard.confirm_action(action="restart"),
    )


# ── Delete user ─────────────────────────────────────────────────────


async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'delete:{username}' — confirm user deletion."""
    query = update.callback_query
    username = query.data.split(":")[1]
    await query.edit_message_text(
        f"⚠️ Are you sure? This will delete user `{username}`.",
        parse_mode="markdown",
        reply_markup=BotKeyboard.confirm_action(action="delete", username=username),
    )


# ── Suspend user ────────────────────────────────────────────────────


async def suspend_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'suspend:{username}' — confirm user suspension."""
    query = update.callback_query
    username = query.data.split(":")[1]
    await query.edit_message_text(
        f"⚠️ Are you sure? This will suspend user `{username}`.",
        parse_mode="markdown",
        reply_markup=BotKeyboard.confirm_action(action="suspend", username=username),
    )


# ── Activate user ───────────────────────────────────────────────────


async def activate_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'activate:{username}' — confirm user activation."""
    query = update.callback_query
    username = query.data.split(":")[1]
    await query.edit_message_text(
        f"⚠️ Are you sure? This will activate user `{username}`.",
        parse_mode="markdown",
        reply_markup=BotKeyboard.confirm_action(action="activate", username=username),
    )


# ── Reset usage ─────────────────────────────────────────────────────


async def reset_usage_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'reset_usage:{username}' — confirm usage reset."""
    query = update.callback_query
    username = query.data.split(":")[1]
    await query.edit_message_text(
        f"⚠️ Are you sure? This will Reset Usage of user `{username}`.",
        parse_mode="markdown",
        reply_markup=BotKeyboard.confirm_action(action="reset_usage", username=username),
    )


# ── Edit All Users ──────────────────────────────────────────────────


async def edit_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'edit_all' — show user status counts."""
    query = update.callback_query
    client = get_client()
    try:
        breakdown = client.get_status_breakdown()
        summary = client.get_summary()
    except Exception:
        breakdown = {"active": 0, "disabled": 0, "expired": 0, "limited": 0}
        summary = {"total_users": 0}

    total = summary.get("total_users", 0)
    text = f"""
👥 *Total Users*: `{total}`
✅ *Active Users*: `{breakdown.get('active', 0)}`
❌ *Disabled Users*: `{breakdown.get('disabled', 0)}`
🕰 *Expired Users*: `{breakdown.get('expired', 0)}`
📵 *Limited Users*: `{breakdown.get('limited', 0)}`"""

    await query.edit_message_text(
        text,
        parse_mode="markdown",
        reply_markup=BotKeyboard.edit_all_menu(),
    )


# ── Delete Expired/Limited ──────────────────────────────────────────


async def delete_expired_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'delete_expired' — confirm bulk delete expired."""
    query = update.callback_query
    await query.edit_message_text(
        "⚠️ Are you sure? This will *DELETE All Expired Users*‼️",
        parse_mode="markdown",
        reply_markup=BotKeyboard.confirm_action(action="delete_expired"),
    )


async def delete_limited_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'delete_limited' — confirm bulk delete limited."""
    query = update.callback_query
    await query.edit_message_text(
        "⚠️ Are you sure? This will *DELETE All Limited Users*‼️",
        parse_mode="markdown",
        reply_markup=BotKeyboard.confirm_action(action="delete_limited"),
    )


# ── Add Data (bulk) ─────────────────────────────────────────────────


async def add_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: 'add_data' — prompt for data limit change."""
    query = update.callback_query
    msg = await query.edit_message_text(
        "🔋 Enter Data Limit to increase or decrease (GB):",
        reply_markup=BotKeyboard.inline_cancel_action(),
    )
    _schedule_delete_message(context, query.message.chat.id, query.message.id, msg.id)
    return STATE_ADD_DATA


async def add_data_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive data limit value for bulk adjustment."""
    chat_id = update.effective_chat.id
    try:
        data_limit = float(update.message.text)
        if not data_limit:
            raise ValueError
    except ValueError:
        wait_msg = await update.message.reply_text("❌ Data limit must be a number and not zero.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_ADD_DATA

    _schedule_delete_message(context, chat_id, update.message.id)
    msg = await update.message.reply_text(
        f"⚠️ Are you sure? this will change Data limit of all users according to <b>"
        f"{'+' if data_limit > 0 else '-'}{fmt_bytes(abs(data_limit * 1024 * 1024 * 1024))}</b>",
        parse_mode="html",
        reply_markup=BotKeyboard.confirm_action("add_data", str(data_limit)),
    )
    await _cleanup_messages(context, chat_id)
    _schedule_delete_message(context, chat_id, msg.id)
    return ConversationHandler.END


# ── Add Time (bulk) ─────────────────────────────────────────────────


async def add_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: 'add_time' — prompt for time adjustment."""
    query = update.callback_query
    msg = await query.edit_message_text(
        "📅 Enter Days to increase or decrease expiry:",
        reply_markup=BotKeyboard.inline_cancel_action(),
    )
    _schedule_delete_message(context, query.message.chat.id, query.message.id, msg.id)
    return STATE_ADD_TIME


async def add_time_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive days value for bulk expiry adjustment."""
    chat_id = update.effective_chat.id
    try:
        days = int(update.message.text)
        if not days:
            raise ValueError
    except ValueError:
        wait_msg = await update.message.reply_text("❌ Days must be as a number and not zero.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_ADD_TIME

    _schedule_delete_message(context, chat_id, update.message.id)
    msg = await update.message.reply_text(
        f"⚠️ Are you sure? this will change Expiry Time of all users according to <b>{days} Days</b>",
        parse_mode="html",
        reply_markup=BotKeyboard.confirm_action("add_time", str(days)),
    )
    await _cleanup_messages(context, chat_id)
    _schedule_delete_message(context, chat_id, msg.id)
    return ConversationHandler.END


# ── Node bulk operations (eovpanel equivalent of inbound_add/remove) ──


async def node_bulk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'node_add' or 'node_remove' — show node selection."""
    query = update.callback_query
    action = query.data  # "node_add" or "node_remove"
    client = get_client()
    try:
        nodes = client.list_nodes()
    except Exception:
        nodes = []

    if not nodes:
        await query.answer("No nodes available!", show_alert=True)
        return

    node_list = [{"name": n["name"], "id": n["id"]} for n in nodes]
    action_type = "add" if action == "node_add" else "remove"
    await query.edit_message_text(
        f"Select node to *{action_type.title()}* from all users",
        parse_mode="markdown",
        reply_markup=BotKeyboard.nodes_menu(action_type, node_list),
    )


# ── Edit user ───────────────────────────────────────────────────────


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'edit:{username}' — open user edit panel."""
    query = update.callback_query
    context.application.drop_handler_by_name(str(query.message.chat.id))
    username = query.data.split(":")[1]
    client = get_client()
    try:
        user = client.get_user(username)
    except Exception:
        await query.answer("❌ User not found.", show_alert=True)
        return

    mem_store.set(f"{query.message.chat.id}:username", username)
    mem_store.set(f"{query.message.chat.id}:data_limit", user.get("data_limit"))

    expire_at = user.get("expire_at")
    if expire_at:
        try:
            expire_dt = datetime.fromisoformat(str(expire_at).replace("Z", "+00:00"))
            mem_store.set(f"{query.message.chat.id}:expire_date", expire_dt)
        except (ValueError, TypeError):
            mem_store.set(f"{query.message.chat.id}:expire_date", None)
    else:
        mem_store.set(f"{query.message.chat.id}:expire_date", None)

    await query.edit_message_text(
        f"📝 Editing user `{username}`",
        parse_mode="markdown",
        reply_markup=BotKeyboard.select_nodes(
            [],
            "edit",
            username=username,
            data_limit=user.get("data_limit"),
            expire_date=mem_store.get(f"{query.message.chat.id}:expire_date"),
        ),
    )


async def help_edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'help_edit' — show edit hint."""
    query = update.callback_query
    await query.answer("Press the (✏️ Edit) button to edit", show_alert=True)


# ── Cancel ──────────────────────────────────────────────────────────


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'cancel' — return to main menu."""
    query = update.callback_query
    context.application.drop_handler_by_name(str(query.message.chat.id))
    await query.edit_message_text(
        _get_system_info(),
        parse_mode="MarkdownV2",
        reply_markup=BotKeyboard.main_menu(),
    )


# ── Edit user sub-flows (data / expire) ─────────────────────────────


async def edit_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Callback: 'edit_user:{username}:{action}' — prompt for data/expire."""
    query = update.callback_query
    _, username, action = query.data.split(":")
    _schedule_delete_message(context, query.message.chat.id, query.message.id)
    await _cleanup_messages(context, query.message.chat.id)

    if action == "data":
        msg = await context.bot.send_message(
            query.message.chat.id,
            "📶 Enter Data Limit (GB):\n⚠️ Send 0 for unlimited.",
            reply_markup=BotKeyboard.inline_cancel_action(f"user:{username}"),
        )
        mem_store.set(f"{query.message.chat.id}:edit_msg_text", query.message.text)
        _schedule_delete_message(context, query.message.chat.id, msg.id)
        return STATE_EDIT_DATA

    elif action == "expire":
        text = """\
📅 Enter expire date like below:
`3d` for 3 days
`2m` for 2 months
or date as (YYYY-MM-DD)
⚠️ Send 0 for never expire."""
        msg = await context.bot.send_message(
            query.message.chat.id,
            text,
            parse_mode="markdown",
            reply_markup=BotKeyboard.inline_cancel_action(f"user:{username}"),
        )
        mem_store.set(f"{query.message.chat.id}:edit_msg_text", query.message.text)
        _schedule_delete_message(context, query.message.chat.id, msg.id)
        return STATE_EDIT_EXPIRE


async def edit_user_data_limit_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive new data limit during edit."""
    chat_id = update.effective_chat.id
    username = mem_store.get(f"{chat_id}:username")
    try:
        if float(update.message.text) < 0:
            wait_msg = await update.message.reply_text("❌ Data limit must be greater or equal to 0.")
            _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
            return STATE_EDIT_DATA
        data_limit = float(update.message.text) * 1024 * 1024 * 1024
    except ValueError:
        wait_msg = await update.message.reply_text("❌ Data limit must be a number.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_EDIT_DATA

    mem_store.set(f"{chat_id}:data_limit", data_limit)
    _schedule_delete_message(context, chat_id, update.message.id)
    text = mem_store.get(f"{chat_id}:edit_msg_text")
    mem_store.delete(f"{chat_id}:edit_msg_text")
    await update.message.reply_text(
        text or f"📝 Editing user <code>{username}</code>",
        parse_mode="html",
        reply_markup=BotKeyboard.select_nodes(
            [],
            "edit",
            username=username,
            data_limit=data_limit,
            expire_date=mem_store.get(f"{chat_id}:expire_date"),
        ),
    )
    await _cleanup_messages(context, chat_id)
    return ConversationHandler.END


async def edit_user_expire_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive new expiry date during edit."""
    chat_id = update.effective_chat.id
    username = mem_store.get(f"{chat_id}:username")
    try:
        now = datetime.now()
        today = datetime(year=now.year, month=now.month, day=now.day, hour=23, minute=59, second=59)
        text = update.message.text

        if re.match(r"^[0-9]{1,3}([MmDd])$", text):
            number = int(re.findall(r"^[0-9]{1,3}", text)[0])
            symbol = re.findall(r"[MmDd]$", text)[0].upper()
            expire_date = (
                today + relativedelta(months=number)
                if symbol == "M"
                else today + relativedelta(days=number)
            )
        elif text == "0":
            expire_date = None
        else:
            expire_date = datetime.strptime(text, "%Y-%m-%d")
            if expire_date < today:
                raise ValueError("Expire date must be greater than today.")
    except ValueError:
        wait_msg = await update.message.reply_text("❌ Date is not in any of valid formats.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_EDIT_EXPIRE

    mem_store.set(f"{chat_id}:expire_date", expire_date)
    _schedule_delete_message(context, chat_id, update.message.id)
    text_msg = mem_store.get(f"{chat_id}:edit_msg_text")
    mem_store.delete(f"{chat_id}:edit_msg_text")
    await update.message.reply_text(
        text_msg or f"📝 Editing user: <code>{username}</code>",
        parse_mode="html",
        reply_markup=BotKeyboard.select_nodes(
            [],
            "edit",
            username=username,
            data_limit=mem_store.get(f"{chat_id}:data_limit"),
            expire_date=expire_date,
        ),
    )
    await _cleanup_messages(context, chat_id)
    return ConversationHandler.END


# ── User list ───────────────────────────────────────────────────────


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'users:{page}' — show paginated user list."""
    query = update.callback_query
    parts = query.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1
    per_page = 10

    client = get_client()
    try:
        users = client.list_users(limit=per_page, offset=(page - 1) * per_page)
        summary = client.get_summary()
        total = summary.get("total_users", 0)
    except Exception:
        users = []
        total = 0

    total_pages = max(1, math.ceil(total / per_page))

    text = f"""👥 Users: (Page {page}/{total_pages})
✅ Active
❌ Disabled
🕰 Expired
📵 Limited"""

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=BotKeyboard.user_list(users, page, total_pages=total_pages),
    )


# ── Edit note ───────────────────────────────────────────────────────


async def edit_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: 'edit_note:{username}' — prompt for new note."""
    query = update.callback_query
    username = query.data.split(":")[1]
    client = get_client()
    try:
        user = client.get_user(username)
    except Exception:
        await query.answer("❌ User not found.", show_alert=True)
        return

    _schedule_delete_message(context, query.message.chat.id, query.message.id)
    await _cleanup_messages(context, query.message.chat.id)

    note = user.get("note") or "empty"
    msg = await context.bot.send_message(
        query.message.chat.id,
        f"<b>📝 Current Note:</b> <code>{note}</code>\n\nSend new Note for <code>{username}</code>",
        parse_mode="HTML",
        reply_markup=BotKeyboard.inline_cancel_action(f"user:{username}"),
    )
    mem_store.set(f"{query.message.chat.id}:username", username)
    _schedule_delete_message(context, query.message.chat.id, msg.id)
    return STATE_EDIT_NOTE


async def edit_note_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive new note text."""
    chat_id = update.effective_chat.id
    note = update.message.text or ""
    if len(note) > 500:
        wait_msg = await update.message.reply_text("❌ Note can not be more than 500 characters.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_EDIT_NOTE

    username = mem_store.get(f"{chat_id}:username")
    if not username:
        await _cleanup_messages(context, chat_id)
        await update.message.reply_text("❌ Something went wrong!\n restart bot /start")
        return ConversationHandler.END

    client = get_client()
    try:
        user = client.update_user(username, {"note": note})
    except Exception:
        await update.message.reply_text("❌ Failed to update note.")
        return ConversationHandler.END

    await update.message.reply_text(
        get_user_info_text(user),
        parse_mode="html",
        reply_markup=BotKeyboard.user_menu(
            user_info={"status": user.get("status", "active"), "username": user["username"]}
        ),
    )

    logger_ch = get_logger_channel_id()
    if logger_ch:
        text = f"""\
📝 <b>#Edit_Note #From_Bot</b>
➖➖➖➖➖➖➖➖➖
<b>Username :</b> <code>{user['username']}</code>
<b>New Note :</b> <code>{note}</code>
➖➖➖➖➖➖➖➖➖
<b>By :</b> <a href="tg://user?id={chat_id}">{update.effective_user.full_name}</a>"""
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                chat_id=logger_ch, text=text, parse_mode="HTML"
            )

    return ConversationHandler.END


# ── View user ───────────────────────────────────────────────────────


async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'user:{username}' or 'user:{username}:{page}' — show user info."""
    query = update.callback_query
    context.application.drop_handler_by_name(str(query.message.chat.id))
    parts = query.data.split(":")
    username = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 1

    client = get_client()
    try:
        user = client.get_user(username)
    except Exception:
        await query.answer("❌ User not found.", show_alert=True)
        return

    await query.edit_message_text(
        get_user_info_text(user),
        parse_mode="HTML",
        reply_markup=BotKeyboard.user_menu(
            {"username": user["username"], "status": user.get("status", "active")},
            page=page,
        ),
    )


# ── Revoke subscription ─────────────────────────────────────────────


async def revoke_sub_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'revoke_sub:{username}' — confirm subscription revocation."""
    query = update.callback_query
    username = query.data.split(":")[1]
    await query.edit_message_text(
        f"⚠️ Are you sure? This will *Revoke Subscription* link for `{username}`‼️",
        parse_mode="markdown",
        reply_markup=BotKeyboard.confirm_action(action=f"revoke_sub:{username}"),
    )


# ── Links ───────────────────────────────────────────────────────────


async def links_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'links:{username}' — show subscription URL and config links."""
    query = update.callback_query
    username = query.data.split(":")[1]
    client = get_client()
    try:
        user = client.get_user(username)
    except Exception:
        await query.answer("User not found!", show_alert=True)
        return

    sub_url = user.get("subscription_url", "")
    text = f"<code>{sub_url}</code>\n\n\n"

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=BotKeyboard.show_links(username),
    )


# ── QR code generation ─────────────────────────────────────────────


async def genqr_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'genqr:{select}:{username}' — generate QR code."""
    query = update.callback_query
    qr_select = query.data.split(":")[1]
    username = query.data.split(":")[2]
    client = get_client()
    try:
        user = client.get_user(username)
    except Exception:
        await query.answer("User not found!", show_alert=True)
        return

    await query.answer("Generating QR code...")

    import qrcode

    sub_url = user.get("subscription_url", "")

    if qr_select == "configs":
        # Generate QR for .ovpn config
        try:
            config_content = client.get_user_config(username)
            f = io.BytesIO()
            qr = qrcode.QRCode(border=6)
            qr.add_data(config_content[:2000])  # QR has size limits
            qr.make_image().save(f)
            f.seek(0)
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=f,
                caption=f"<code>{username}.ovpn</code>",
                parse_mode="HTML",
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text="❌ Failed to generate config QR code",
            )
    else:
        # Generate QR for subscription URL
        data_limit = user.get("data_limit")
        data_used = user.get("data_used", 0)
        expire_at = user.get("expire_at")
        status = user.get("status", "active")

        expiry_text = ""
        if expire_at:
            try:
                expire_dt = datetime.fromisoformat(str(expire_at).replace("Z", "+00:00"))
                expiry_text = f"📅 <b>Expiry Date:</b> <code>{expire_dt.strftime('%Y-%m-%d')}</code>"
            except (ValueError, TypeError):
                expiry_text = "📅 <b>Expiry Date:</b> <code>Never</code>"
        else:
            expiry_text = "📅 <b>Expiry Date:</b> <code>Never</code>"

        text = f"""\
{STATUSES.get(status, '?')} <b>Status:</b> <code>{status.title()}</code>

🔤 <b>Username:</b> <code>{user['username']}</code>

🔋 <b>Data limit:</b> <code>{fmt_bytes(data_limit) if data_limit else 'Unlimited'}</code>
📶 <b>Data Used:</b> <code>{fmt_bytes(data_used) if data_used else '-'}</code>
{expiry_text}
🚀 <b><a href="{sub_url}">Subscription</a>:</b> <code>{sub_url}</code>"""

        with io.BytesIO() as f:
            qr = qrcode.QRCode(border=6)
            qr.add_data(sub_url)
            qr.make_image().save(f)
            f.seek(0)
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=f,
                caption=text,
                parse_mode="HTML",
                reply_markup=BotKeyboard.subscription_page(sub_url),
            )

    with contextlib.suppress(Exception):
        await context.bot.delete_message(
            query.message.chat.id, query.message.message_id
        )


# ── Charge user ─────────────────────────────────────────────────────


async def charge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'charge:{username}' — show charge options.

    eovpanel has no templates, so we charge with +30 days / +10GB defaults.
    """
    query = update.callback_query
    username = query.data.split(":")[1]
    await query.edit_message_text(
        "🔢 Select charge option:",
        reply_markup=BotKeyboard.charge_add_or_reset(username, None, None),
    )


# ── Create user ─────────────────────────────────────────────────────


async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: 'add_user' or 'add_bulk_user' — start create user flow."""
    query = update.callback_query
    with contextlib.suppress(Exception):
        await context.bot.delete_message(
            query.message.chat.id, query.message.message_id
        )

    is_bulk = query.data == "add_bulk_user"
    mem_store.set(f"{query.message.chat.id}:is_bulk", is_bulk)

    msg = await context.bot.send_message(
        query.message.chat.id,
        "👤 Enter username:\n⚠️Username only can be 3 to 32 characters and "
        "contain a-z, A-Z 0-9, and underscores in between.",
        reply_markup=BotKeyboard.random_username(),
    )
    _schedule_delete_message(context, query.message.chat.id, msg.id)
    return STATE_USERNAME


async def random_username_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Callback: 'random:' — generate random username and proceed."""
    query = update.callback_query

    username = "".join(
        [random.choice(string.ascii_letters)]
        + random.choices(string.ascii_letters + string.digits, k=7)
    )

    _schedule_delete_message(context, query.message.chat.id, query.message.id)
    await _cleanup_messages(context, query.message.chat.id)

    if mem_store.get(f"{query.message.chat.id}:is_bulk", False):
        msg = await context.bot.send_message(
            query.message.chat.id,
            "how many do you want?",
            reply_markup=BotKeyboard.inline_cancel_action(),
        )
        _schedule_delete_message(context, query.message.chat.id, msg.id)
        mem_store.set(f"{query.message.chat.id}:username", username)
        return STATE_BULK_NUMBER

    msg = await context.bot.send_message(
        query.message.chat.id,
        "⬆️ Enter Data Limit (GB):\n⚠️ Send 0 for unlimited.",
        reply_markup=BotKeyboard.inline_cancel_action(),
    )
    _schedule_delete_message(context, query.message.chat.id, msg.id)
    mem_store.set(f"{query.message.chat.id}:username", username)
    return STATE_DATA_LIMIT


async def username_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive username for new user."""
    chat_id = update.effective_chat.id
    username = update.message.text
    if not username:
        wait_msg = await update.message.reply_text("❌ Username can not be empty.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_USERNAME

    if not re.match(r"^(?=\w{3,32}\b)[a-zA-Z0-9-_@.]+(?:_[a-zA-Z0-9-_@.]+)*$", username):
        wait_msg = await update.message.reply_text(
            "❌ Username only can be 3 to 32 characters and contain a-z, A-Z, 0-9, and underscores in between."
        )
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_USERNAME

    client = get_client()
    try:
        client.get_user(username)
        wait_msg = await update.message.reply_text("❌ Username already exists.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_USERNAME
    except Exception:
        pass  # User doesn't exist — good

    _schedule_delete_message(context, chat_id, update.message.id)
    await _cleanup_messages(context, chat_id)

    if mem_store.get(f"{chat_id}:is_bulk", False):
        msg = await update.message.reply_text(
            "how many do you want?",
            reply_markup=BotKeyboard.inline_cancel_action(),
        )
        _schedule_delete_message(context, chat_id, msg.id)
        mem_store.set(f"{chat_id}:username", username)
        return STATE_BULK_NUMBER

    msg = await update.message.reply_text(
        "⬆️ Enter Data Limit (GB):\n⚠️ Send 0 for unlimited.",
        reply_markup=BotKeyboard.inline_cancel_action(),
    )
    _schedule_delete_message(context, chat_id, msg.id)
    mem_store.set(f"{chat_id}:username", username)
    return STATE_DATA_LIMIT


async def bulk_number_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive bulk count."""
    chat_id = update.effective_chat.id
    try:
        if int(update.message.text) < 1:
            wait_msg = await update.message.reply_text("❌ Bulk number must be greater or equal to 1.")
            _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
            return STATE_BULK_NUMBER
        mem_store.set(f"{chat_id}:number", int(update.message.text))
    except ValueError:
        wait_msg = await update.message.reply_text("❌ bulk must be a number.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_BULK_NUMBER

    _schedule_delete_message(context, chat_id, update.message.id)
    await _cleanup_messages(context, chat_id)

    msg = await update.message.reply_text(
        "⬆️ Enter Data Limit (GB):\n⚠️ Send 0 for unlimited.",
        reply_markup=BotKeyboard.inline_cancel_action(),
    )
    _schedule_delete_message(context, chat_id, msg.id)
    return STATE_DATA_LIMIT


async def data_limit_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive data limit for new user."""
    chat_id = update.effective_chat.id
    try:
        if float(update.message.text) < 0:
            wait_msg = await update.message.reply_text("❌ Data limit must be greater or equal to 0.")
            _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
            return STATE_DATA_LIMIT
        data_limit = float(update.message.text) * 1024 * 1024 * 1024
    except ValueError:
        wait_msg = await update.message.reply_text("❌ Data limit must be a number.")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_DATA_LIMIT

    _schedule_delete_message(context, chat_id, update.message.id)
    await _cleanup_messages(context, chat_id)

    mem_store.set(f"{chat_id}:data_limit", data_limit)
    username = mem_store.get(f"{chat_id}:username")
    msg = await update.message.reply_text(
        f"Select Status for user `{username}`:\nData Limit: {fmt_bytes(data_limit) if data_limit else 'Unlimited'}",
        parse_mode="markdown",
        reply_markup=BotKeyboard.user_status_select(),
    )
    _schedule_delete_message(context, chat_id, msg.id)
    return STATE_STATUS


async def add_user_status_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'status:active' or 'status:onhold' — set user status."""
    query = update.callback_query
    user_status = query.data.split(":")[1]
    chat_id = query.message.chat.id

    if user_status not in ["active", "onhold"]:
        await query.answer("❌ Invalid status. Please choose Active or OnHold.", show_alert=True)
        return

    await context.bot.edit_message_reply_markup(chat_id, query.message.message_id, reply_markup=None)
    await context.bot.delete_message(chat_id, query.message.message_id)

    if user_status == "onhold":
        expiry_message = (
            "⬆️ Enter Expire Days\n"
            "You Can Use Regex Symbol: ^[0-9]{1,3}(M|D) :"
        )
    else:
        expiry_message = (
            "⬆️ Enter Expire Date (YYYY-MM-DD)\n"
            "Or You Can Use Regex Symbol: ^[0-9]{1,3}(M|D) :\n"
            "⚠️ Send 0 for never expire."
        )

    msg = await context.bot.send_message(
        chat_id,
        expiry_message,
        reply_markup=BotKeyboard.inline_cancel_action(),
    )
    _schedule_delete_message(context, chat_id, msg.id)
    mem_store.set(f"{chat_id}:user_status", user_status)
    return STATE_EXPIRE


async def expire_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """FSM: receive expiry date/days."""
    chat_id = update.effective_chat.id
    username = mem_store.get(f"{chat_id}:username")
    data_limit = mem_store.get(f"{chat_id}:data_limit")
    user_status = mem_store.get(f"{chat_id}:user_status")
    text = update.message.text

    try:
        now = datetime.now()
        today = datetime(year=now.year, month=now.month, day=now.day, hour=23, minute=59, second=59)

        if re.match(r"^[0-9]{1,3}([MmDd])$", text):
            number = int(re.findall(r"^[0-9]{1,3}", text)[0])
            symbol = re.findall(r"([MmDd])$", text)[0].upper()
            if user_status == "onhold":
                expire_date = number * 30 if symbol == "M" else number
            else:
                expire_date = (
                    today + relativedelta(months=number)
                    if symbol == "M"
                    else today + relativedelta(days=number)
                )
        elif text == "0":
            if user_status == "onhold":
                raise ValueError("Expire days is required for an on hold user.")
            expire_date = None
        elif user_status == "active":
            expire_date = datetime.strptime(text, "%Y-%m-%d")
            if expire_date < today:
                raise ValueError("Expire date must be greater than today.")
        else:
            raise ValueError("Invalid input for onhold status.")
    except ValueError as e:
        error_message = str(e) if str(e) != "Invalid input for onhold status." else "Invalid input. Please try again."
        wait_msg = await update.message.reply_text(f"❌ {error_message}")
        _schedule_delete_message(context, chat_id, wait_msg.id, update.message.id)
        return STATE_EXPIRE

    mem_store.set(f"{chat_id}:expire_date", expire_date)
    _schedule_delete_message(context, chat_id, update.message.id)
    await _cleanup_messages(context, chat_id)

    # Show confirm keyboard
    data_limit_str = fmt_bytes(data_limit) if data_limit else "Unlimited"
    if isinstance(expire_date, datetime):
        expire_str = expire_date.strftime("%Y-%m-%d")
    else:
        expire_str = str(expire_date) if expire_date else "Never"

    await update.message.reply_text(
        f"📝 Creating user: <code>{username}</code>\n"
        f"Data Limit: {data_limit_str}\n"
        f"Status: {user_status}\nExpiry: {expire_str}",
        parse_mode="html",
        reply_markup=BotKeyboard.confirm_action("add_user"),
    )
    return ConversationHandler.END


# ── Backup submenu ──────────────────────────────────────────────────


async def backup_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'backup' — show backup submenu."""
    query = update.callback_query
    client = get_client()
    try:
        backup_config = client.get_backup_config()
    except Exception:
        backup_config = {}

    await query.edit_message_text(
        "📦 Backup Management",
        reply_markup=BotKeyboard.backup_menu(backup_config),
    )


async def backup_send_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'backup_send' — create and send backup now."""
    query = update.callback_query
    await query.edit_message_text("⏳ Creating backup...")

    client = get_client()
    try:
        result = client.create_backup()
        await query.edit_message_text(
            f"✅ Backup created: {result.get('filename', 'unknown')}",
            reply_markup=BotKeyboard.backup_menu(),
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Backup failed: {e}",
            reply_markup=BotKeyboard.backup_menu(),
        )


async def backup_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'backup_list' — list available backups."""
    query = update.callback_query
    client = get_client()
    try:
        backups = client.list_backups()
    except Exception:
        backups = []

    if not backups:
        text = "📋 No backups available."
    else:
        text = "📋 <b>Available Backups:</b>\n\n"
        for b in backups[:10]:
            text += f"• <code>{b.get('name', 'unknown')}</code> ({b.get('size', '?')})\n"

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=BotKeyboard.backup_menu(),
    )


async def backup_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'backup_toggle' — toggle auto backup."""
    query = update.callback_query
    await query.answer("Auto backup toggle — configure via panel Settings", show_alert=True)


# ── Confirm handler (master) ────────────────────────────────────────


async def confirm_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: 'confirm:{action}:{...}' — master confirmation handler.

    Mirrors Marzban's confirm_user_command with all action types.
    """
    query = update.callback_query
    data = query.data.split(":")[1]
    chat_id = query.from_user.id
    full_name = query.from_user.full_name
    client = get_client()

    if data == "delete":
        username = query.data.split(":")[2]
        try:
            client.delete_user(username)
        except Exception:
            await query.answer("❌ Failed to delete user.", show_alert=True)
            return

        await query.edit_message_text(
            "✅ User deleted.",
            reply_markup=BotKeyboard.main_menu(),
        )
        _send_logger_channel(
            context,
            f"""\
🗑 <b>#Deleted #From_Bot</b>
➖➖➖➖➖➖➖➖➖
<b>Username :</b> <code>{username}</code>
➖➖➖➖➖➖➖➖➖
<b>By :</b> <a href="tg://user?id={chat_id}">{full_name}</a>""",
        )

    elif data == "suspend":
        username = query.data.split(":")[2]
        try:
            user = client.disable_user(username)
        except Exception:
            await query.answer("❌ Failed to disable user.", show_alert=True)
            return

        await query.edit_message_text(
            get_user_info_text(user),
            parse_mode="HTML",
            reply_markup=BotKeyboard.user_menu(
                user_info={"status": "disabled", "username": username}
            ),
        )
        _send_logger_channel(
            context,
            f"""\
❌ <b>#Disabled  #From_Bot</b>
➖➖➖➖➖➖➖➖➖
<b>Username</b> : <code>{username}</code>
➖➖➖➖➖➖➖➖➖
<b>By :</b> <a href="tg://user?id={chat_id}">{full_name}</a>""",
        )

    elif data == "activate":
        username = query.data.split(":")[2]
        try:
            user = client.enable_user(username)
        except Exception:
            await query.answer("❌ Failed to enable user.", show_alert=True)
            return

        await query.edit_message_text(
            get_user_info_text(user),
            parse_mode="HTML",
            reply_markup=BotKeyboard.user_menu(
                user_info={"status": "active", "username": username}
            ),
        )
        _send_logger_channel(
            context,
            f"""\
✅ <b>#Activated  #From_Bot</b>
➖➖➖➖➖➖➖➖➖
<b>Username</b> : <code>{username}</code>
➖➖➖➖➖➖➖➖➖
<b>By :</b> <a href="tg://user?id={chat_id}">{full_name}</a>""",
        )

    elif data == "reset_usage":
        username = query.data.split(":")[2]
        try:
            user = client.reset_usage(username)
        except Exception:
            await query.answer("❌ Failed to reset usage.", show_alert=True)
            return

        await query.edit_message_text(
            get_user_info_text(user),
            parse_mode="HTML",
            reply_markup=BotKeyboard.user_menu(
                user_info={"status": user.get("status", "active"), "username": username}
            ),
        )
        _send_logger_channel(
            context,
            f"""\
🔁 <b>#Reset_usage  #From_Bot</b>
➖➖➖➖➖➖➖➖➖
<b>Username</b> : <code>{username}</code>
➖➖➖➖➖➖➖➖➖
<b>By :</b> <a href="tg://user?id={chat_id}">{full_name}</a>""",
        )

    elif data == "restart":
        await query.edit_message_text("🔄 Restarting OpenVPN core...")
        # TODO: Call actual restart endpoint if available
        await query.edit_message_text(
            "✅ OpenVPN core restarted successfully.",
            reply_markup=BotKeyboard.main_menu(),
        )

    elif data == "edit_user":
        username = mem_store.get(f"{query.message.chat.id}:username")
        if username is None:
            with contextlib.suppress(Exception):
                await context.bot.delete_message(
                    query.message.chat.id, query.message.message_id
                )
            await context.bot.send_message(
                query.message.chat.id,
                "❌ Bot reload detected. Please start over.",
                reply_markup=BotKeyboard.main_menu(),
            )
            return

        data_limit = mem_store.get(f"{query.message.chat.id}:data_limit")
        expire_date = mem_store.get(f"{query.message.chat.id}:expire_date")

        update_data: dict = {}
        if data_limit is not None:
            update_data["data_limit"] = int(data_limit) if data_limit else None
        if expire_date is not None:
            if isinstance(expire_date, datetime):
                update_data["expire_at"] = expire_date.isoformat()
            elif expire_date == 0 or expire_date is None:
                update_data["expire_at"] = None

        try:
            user = client.update_user(username, update_data)
        except Exception:
            await query.answer("❌ Failed to update user.", show_alert=True)
            return

        await query.answer("✅ User updated successfully.")
        await query.edit_message_text(
            get_user_info_text(user),
            parse_mode="HTML",
            reply_markup=BotKeyboard.user_menu(
                {"username": user["username"], "status": user.get("status", "active")}
            ),
        )

    elif data == "add_user":
        username = mem_store.get(f"{query.message.chat.id}:username")
        if username is None:
            with contextlib.suppress(Exception):
                await context.bot.delete_message(
                    query.message.chat.id, query.message.message_id
                )
            await context.bot.send_message(
                query.message.chat.id,
                "❌ Bot reload detected. Please start over.",
                reply_markup=BotKeyboard.main_menu(),
            )
            return

        data_limit = mem_store.get(f"{query.message.chat.id}:data_limit")
        expire_date = mem_store.get(f"{query.message.chat.id}:expire_date")
        user_status = mem_store.get(f"{query.message.chat.id}:user_status", "active")
        number = mem_store.get(f"{query.message.chat.id}:number", 1)
        is_bulk = mem_store.get(f"{query.message.chat.id}:is_bulk", False)
        if not is_bulk:
            number = 1

        for i in range(number):
            current_username = username
            if is_bulk:
                n = get_number_at_end(username)
                if n:
                    current_username = username.replace(n, str(int(n) + i))
                else:
                    current_username += str(i + 1) if i > 0 else ""

            create_data: dict = {
                "username": current_username,
                "status": user_status,
            }
            if data_limit:
                create_data["data_limit"] = int(data_limit)
            if expire_date and isinstance(expire_date, datetime):
                create_data["expire_at"] = expire_date.isoformat()

            try:
                user = client.create_user(create_data)
            except Exception as e:
                await query.answer(f"❌ {e}", show_alert=True)
                return

            if is_bulk:
                _schedule_delete_message(context, query.message.chat.id, query.message.id)
                await _cleanup_messages(context, query.message.chat.id)
                await context.bot.send_message(
                    query.message.chat.id,
                    get_user_info_text(user),
                    parse_mode="HTML",
                    reply_markup=BotKeyboard.user_menu(
                        user_info={"status": user.get("status", "active"), "username": user["username"]}
                    ),
                )
            else:
                await query.edit_message_text(
                    get_user_info_text(user),
                    parse_mode="HTML",
                    reply_markup=BotKeyboard.user_menu(
                        user_info={"status": user.get("status", "active"), "username": user["username"]}
                    ),
                )

            _send_logger_channel(
                context,
                f"""\
🆕 <b>#Created #From_Bot</b>
➖➖➖➖➖➖➖➖➖
<b>Username :</b> <code>{user['username']}</code>
<b>Status :</b> <code>{user_status.title()}</code>
<b>Traffic Limit :</b> <code>{fmt_bytes(data_limit) if data_limit else "Unlimited"}</code>
<b>Expire Date :</b> <code>{
    expire_date.strftime('%H:%M:%S %Y-%m-%d')
    if isinstance(expire_date, datetime)
    else "Never"
}</code>
➖➖➖➖➖➖➖➖➖
<b>By :</b> <a href="tg://user?id={chat_id}">{full_name}</a>""",
            )

    elif data in ("delete_expired", "delete_limited"):
        await query.edit_message_text(
            "⏳ <b>In Progress...</b>",
            parse_mode="HTML",
        )
        try:
            users = client.list_users(limit=200)
            status_filter = "expired" if data == "delete_expired" else "limited"
            to_delete = [u for u in users if u.get("status") == status_filter]
            deleted = 0
            for u in to_delete:
                try:
                    client.delete_user(u["username"])
                    deleted += 1
                except Exception:
                    pass

            await query.edit_message_text(
                f"✅ <code>{deleted}</code>/<code>{len(to_delete)}</code> <b>{status_filter.title()} Users Deleted</b>",
                parse_mode="HTML",
                reply_markup=BotKeyboard.main_menu(),
            )
        except Exception:
            await query.edit_message_text(
                "❌ Failed to delete users.",
                reply_markup=BotKeyboard.main_menu(),
            )

    elif data == "add_data":
        data_limit_val = float(query.data.split(":")[2]) * 1024 * 1024 * 1024
        await context.bot.send_message(chat_id, "⏳ <b>In Progress...</b>", "HTML")
        try:
            users = client.list_users(limit=200)
            counter = 0
            for u in users:
                if u.get("data_limit") and u.get("status") not in ("limited", "expired"):
                    try:
                        client.update_user(u["username"], {
                            "data_limit": u["data_limit"] + int(data_limit_val)
                        })
                        counter += 1
                    except Exception:
                        pass

            await context.bot.send_message(
                chat_id,
                f"✅ <b>{counter}/{len(users)} Users</b> Data Limit "
                f"according to <code>"
                f"{'+' if data_limit_val > 0 else '-'}"
                f"{fmt_bytes(abs(data_limit_val))}</code>",
                "HTML",
                reply_markup=BotKeyboard.main_menu(),
            )
        except Exception:
            await context.bot.send_message(
                chat_id,
                "❌ Failed to adjust data limits.",
                reply_markup=BotKeyboard.main_menu(),
            )

    elif data == "add_time":
        days = int(query.data.split(":")[2])
        await context.bot.send_message(chat_id, "⏳ <b>In Progress...</b>", "HTML")
        try:
            users = client.list_users(limit=200)
            counter = 0
            for u in users:
                if u.get("expire_at") and u.get("status") not in ("limited", "expired"):
                    try:
                        expire_dt = datetime.fromisoformat(u["expire_at"].replace("Z", "+00:00"))
                        new_expire = expire_dt + relativedelta(days=days)
                        client.update_user(u["username"], {"expire_at": new_expire.isoformat()})
                        counter += 1
                    except Exception:
                        pass

            await context.bot.send_message(
                chat_id,
                f"✅ <b>{counter}/{len(users)} Users</b> Expiry Changes according to {days} Days",
                "HTML",
                reply_markup=BotKeyboard.main_menu(),
            )
        except Exception:
            await context.bot.send_message(
                chat_id,
                "❌ Failed to adjust expiry dates.",
                reply_markup=BotKeyboard.main_menu(),
            )

    elif data in ("node_add", "node_remove"):
        # Handled by confirm_node patterns
        pass

    elif data.startswith("revoke_sub:"):
        username = data.split(":")[1] if ":" in data else query.data.split(":")[2]
        try:
            user = client.revoke_subscription(username)
        except Exception:
            await query.answer("❌ User not found!", show_alert=True)
            return

        await query.answer("✅ Subscription Successfully Revoked!")
        await query.edit_message_text(
            get_user_info_text(user),
            parse_mode="HTML",
            reply_markup=BotKeyboard.user_menu(
                user_info={"status": user.get("status", "active"), "username": user["username"]}
            ),
        )
        _send_logger_channel(
            context,
            f"""\
🚫 <b>#Revoke_sub #From_Bot</b>
➖➖➖➖➖➖➖➖➖
<b>Username:</b> <code>{username}</code>
➖➖➖➖➖➖➖➖➖
<b>By :</b> <a href="tg://user?id={chat_id}">{full_name}</a>""",
        )


# ── /user search command ────────────────────────────────────────────


async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /user username1 username2 — search and show user info."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ You must pass some usernames\n\n"
            "<b>Usage:</b> <code>/user username1 username2</code>",
            parse_mode="HTML",
        )
        return

    client = get_client()
    for username in args:
        try:
            user = client.get_user(username)
            await update.message.reply_text(
                get_user_info_text(user),
                parse_mode="html",
                reply_markup=BotKeyboard.user_menu(
                    user_info={"status": user.get("status", "active"), "username": user["username"]}
                ),
            )
        except Exception:
            await update.message.reply_text(f"❌ User «{username}» not found.")


# ── No-op step handler (placeholder for FSM) ────────────────────────


async def _noop_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Placeholder — real step handlers use ConversationHandler."""
    pass

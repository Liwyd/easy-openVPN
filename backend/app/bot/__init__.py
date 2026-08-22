"""Interactive Telegram bot — full Marzban-clone admin panel + notifications + backups.

This module replaces the notification-only bot with a fully interactive
Telegram bot that mirrors Marzban's admin panel.  It runs via long-polling
in a daemon thread started during FastAPI application startup.

The single bot handles:
  - Admin control panel (user CRUD, system info, bulk operations)
  - All notification events (Marzban-style formatted messages)
  - Backup management (scheduled + manual, merged from Marzban's
    separate backup bot into this single bot)

Architecture:
  - Uses python-telegram-bot v21+ (async) running in its own thread
  - Communicates with the FastAPI panel via HTTP API (api_client.py)
  - No direct database access — thread-safe by design
"""

from __future__ import annotations

import logging
from threading import Thread

from telegram.ext import ApplicationBuilder

from app.bot.config import get_config

logger = logging.getLogger(__name__)

_application = None


def get_application():
    """Return the running python-telegram-bot Application instance."""
    return _application


def start_bot() -> None:
    """Start the interactive Telegram bot in a daemon thread.

    Called from FastAPI startup event.  If Telegram is not configured,
    this is a no-op.
    """
    global _application

    cfg = get_config()
    if not cfg.get("enabled") or not cfg.get("bot_token"):
        logger.info("Telegram bot disabled — skipping startup")
        return

    token = cfg["bot_token"]
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is empty — bot not started")
        return

    _application = (
        ApplicationBuilder()
        .token(token)
        .build()
    )

    _register_handlers(_application)

    def _run_polling():
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            await _application.initialize()
            await _application.start()
            await _application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=[
                    "message",
                    "callback_query",
                    "inline_query",
                ],
            )
            logger.info("Telegram bot long-polling started")

            # Block until the thread is stopped (daemon thread)
            await asyncio.Event().wait()

        loop.run_until_complete(_run())

    thread = Thread(target=_run_polling, daemon=True, name="telegram-bot")
    thread.start()
    logger.info("Telegram bot thread started")


def _register_handlers(app) -> None:
    """Register all command, callback, and FSM handlers on the Application."""
    from telegram.ext import (
        CallbackQueryHandler,
        CommandHandler,
        ConversationHandler,
        MessageHandler,
        filters,
    )

    from app.bot.handlers import admin as admin_module
    from app.bot.handlers import user as user_module
    from app.bot.utils.custom_filters import is_admin

    _add = app.add_handler

    def _admin_only(callback):
        """Wrap a handler callback to reject non-admin updates."""
        async def wrapper(update, context):
            if not is_admin.filter(update):
                return
            return await callback(update, context)
        wrapper.__name__ = callback.__name__
        return wrapper

    # ── FSM ConversationHandlers (must come first) ─────────────────
    # Marzban uses register_next_step_handler (telebot); we map to
    # ConversationHandler states per the Step 0 architectural rule.

    # Create user flow: username → bulk_number → data_limit → status → expire
    conv_create = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _admin_only(admin_module.add_user_command),
                pattern=r"^(add_user|add_bulk_user)$",
            ),
            CallbackQueryHandler(
                _admin_only(admin_module.random_username_callback),
                pattern=r"^random",
            ),
        ],
        states={
            admin_module.STATE_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.username_step),
            ],
            admin_module.STATE_BULK_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.bulk_number_step),
            ],
            admin_module.STATE_DATA_LIMIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.data_limit_step),
            ],
            admin_module.STATE_STATUS: [
                CallbackQueryHandler(
                    _admin_only(admin_module.add_user_status_step),
                    pattern=r"^status:",
                ),
            ],
            admin_module.STATE_EXPIRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.expire_step),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(_admin_only(admin_module.cancel_command), pattern=r"^cancel$"),
        ],
        per_message=False,
        per_chat=True,
    )

    # Edit user data limit
    conv_edit_data = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _admin_only(admin_module.edit_user_command),
                pattern=r"^edit_user:.*:data$",
            ),
        ],
        states={
            admin_module.STATE_EDIT_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.edit_user_data_limit_step),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(_admin_only(admin_module.cancel_command), pattern=r"^cancel$"),
        ],
        per_message=False,
        per_chat=True,
    )

    # Edit user expire
    conv_edit_expire = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _admin_only(admin_module.edit_user_command),
                pattern=r"^edit_user:.*:expire$",
            ),
        ],
        states={
            admin_module.STATE_EDIT_EXPIRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.edit_user_expire_step),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(_admin_only(admin_module.cancel_command), pattern=r"^cancel$"),
        ],
        per_message=False,
        per_chat=True,
    )

    # Edit note
    conv_edit_note = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _admin_only(admin_module.edit_note_command),
                pattern=r"^edit_note:",
            ),
        ],
        states={
            admin_module.STATE_EDIT_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.edit_note_step),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(_admin_only(admin_module.cancel_command), pattern=r"^cancel$"),
        ],
        per_message=False,
        per_chat=True,
    )

    # Bulk add data
    conv_add_data = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _admin_only(admin_module.add_data_command),
                pattern=r"^add_data$",
            ),
        ],
        states={
            admin_module.STATE_ADD_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.add_data_step),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(_admin_only(admin_module.cancel_command), pattern=r"^cancel$"),
        ],
        per_message=False,
        per_chat=True,
    )

    # Bulk add time
    conv_add_time = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _admin_only(admin_module.add_time_command),
                pattern=r"^add_time$",
            ),
        ],
        states={
            admin_module.STATE_ADD_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_module.add_time_step),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(_admin_only(admin_module.cancel_command), pattern=r"^cancel$"),
        ],
        per_message=False,
        per_chat=True,
    )

    # ConversationHandlers MUST be added before other handlers so they
    # get first crack at matching messages/callbacks.
    _add(conv_create)
    _add(conv_edit_data)
    _add(conv_edit_expire)
    _add(conv_edit_note)
    _add(conv_add_data)
    _add(conv_add_time)

    # ── Commands ──────────────────────────────────────────────────────
    _add(CommandHandler("start", admin_module.help_command, filters=is_admin))
    _add(CommandHandler("help", admin_module.help_command, filters=is_admin))
    _add(CommandHandler("usage", user_module.usage_command))
    _add(CommandHandler("user", admin_module.search_user, filters=is_admin))

    # ── Callback queries (admin only) ─────────────────────────────────
    # System / restart
    _add(CallbackQueryHandler(_admin_only(admin_module.system_command), pattern="^system$"))
    _add(CallbackQueryHandler(_admin_only(admin_module.restart_command), pattern="^restart$"))
    _add(CallbackQueryHandler(_admin_only(admin_module.cancel_command), pattern="^cancel$"))
    _add(CallbackQueryHandler(_admin_only(admin_module.help_edit_command), pattern="^help_edit$"))

    # User list / pagination
    _add(CallbackQueryHandler(_admin_only(admin_module.users_command), pattern=r"^users:"))
    _add(CallbackQueryHandler(_admin_only(admin_module.user_command), pattern=r"^user:"))

    # User actions
    _add(CallbackQueryHandler(
        _admin_only(admin_module.delete_user_command), pattern=r"^delete:"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.suspend_user_command), pattern=r"^suspend:"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.activate_user_command), pattern=r"^activate:"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.reset_usage_user_command), pattern=r"^reset_usage:"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.revoke_sub_command), pattern=r"^revoke_sub:"))

    # User management
    _add(CallbackQueryHandler(_admin_only(admin_module.edit_command), pattern=r"^edit:"))
    _add(CallbackQueryHandler(_admin_only(admin_module.links_command), pattern=r"^links:"))
    _add(CallbackQueryHandler(_admin_only(admin_module.genqr_command), pattern=r"^genqr:"))
    _add(CallbackQueryHandler(_admin_only(admin_module.charge_command), pattern=r"^charge:"))

    # Edit all users
    _add(CallbackQueryHandler(
        _admin_only(admin_module.edit_all_command), pattern="^edit_all$"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.delete_expired_command), pattern="^delete_expired$"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.delete_limited_command), pattern="^delete_limited$"))

    # Node bulk operations (eovpanel equivalent of inbound_add/inbound_remove)
    _add(CallbackQueryHandler(_admin_only(admin_module.node_bulk_command), pattern=r"^node_"))

    # Confirmation handler (must be registered LAST for confirm: patterns)
    _add(CallbackQueryHandler(_admin_only(admin_module.confirm_user_command), pattern=r"^confirm:"))

    # Backup submenu
    _add(CallbackQueryHandler(
        _admin_only(admin_module.backup_menu_command), pattern="^backup$"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.backup_send_command), pattern="^backup_send$"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.backup_list_command), pattern="^backup_list$"))
    _add(CallbackQueryHandler(
        _admin_only(admin_module.backup_toggle_command), pattern="^backup_toggle$"))

    logger.info("Telegram bot handlers registered")


# ── Notification interface (used by event bus) ─────────────────────────

def send_notification(text: str, chat_id: int | None = None, reply_markup=None) -> None:
    """Send a notification message via the bot.

    Replaces the old httpx-based send_message_plain() for notification
    delivery.  Falls back to httpx if the bot is not running.
    """
    import asyncio

    app = get_application()
    if app is None:
        from app.bot.client import send_message_plain
        send_message_plain(text)
        return

    from app.bot.config import get_admin_chat_ids, get_logger_channel_id

    targets: list[int] = []
    logger_ch = get_logger_channel_id()
    if logger_ch:
        targets.append(logger_ch)
    else:
        for cid in get_admin_chat_ids():
            try:
                targets.append(int(cid))
            except (ValueError, TypeError):
                continue

    if chat_id:
        targets.append(chat_id)

    async def _send():
        for tid in set(targets):
            try:
                await app.bot.send_message(
                    chat_id=tid,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            except Exception:
                logger.warning("Failed to send notification to %s", tid, exc_info=True)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send())
    except RuntimeError:
        asyncio.run(_send())

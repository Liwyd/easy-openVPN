"""add_telegram_config

Revision ID: e1d2c3b4a5f6
Revises: d9e8f7a6b5c4
Create Date: 2026-08-12 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1d2c3b4a5f6"
down_revision: str | Sequence[str] | None = "d9e8f7a6b5c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Panel-managed Telegram bot settings (single row, id=1).
    op.create_table(
        "telegram_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("bot_token", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("admin_chat_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("telegram_config")

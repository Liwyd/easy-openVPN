"""add_backup_config

Revision ID: c8d7e6f5a4b3
Revises: b7c6d5e4f3a2
Create Date: 2026-08-11 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d7e6f5a4b3"
down_revision: str | Sequence[str] | None = "b7c6d5e4f3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Scheduled-backup settings (single row, id=1).
    op.create_table(
        "backup_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("schedule_hour", sa.Integer, nullable=False, server_default="3"),
        sa.Column("schedule_minute", sa.Integer, nullable=False, server_default="0"),
        sa.Column("send_to_telegram", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("keep_count", sa.Integer, nullable=False, server_default="7"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_backup_file", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("backup_config")

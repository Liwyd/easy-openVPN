"""add_openvpn_advanced_fields

Revision ID: a8b9c0d1e2f3
Revises: f2a3b4c5d6e7
Create Date: 2026-08-21 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── server_config: add backup remote, advanced directives ─────────
    op.add_column("server_config", sa.Column("backup_host", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("server_config", sa.Column("backup_port", sa.Integer, nullable=False, server_default="0"))
    op.add_column("server_config", sa.Column("reneg_sec", sa.Integer, nullable=False, server_default="3600"))
    op.add_column("server_config", sa.Column("connect_retry", sa.Integer, nullable=False, server_default="1"))
    op.add_column("server_config", sa.Column("mute_replay_warnings", sa.Boolean, nullable=False, server_default="1"))

    # ── users: add OpenVPN password ──────────────────────────────────
    op.add_column("users", sa.Column("ovpn_password", sa.String(length=255), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("users", "ovpn_password")

    op.drop_column("server_config", "mute_replay_warnings")
    op.drop_column("server_config", "connect_retry")
    op.drop_column("server_config", "reneg_sec")
    op.drop_column("server_config", "backup_port")
    op.drop_column("server_config", "backup_host")

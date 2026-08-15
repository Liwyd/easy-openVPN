"""add_admin_nodes

Revision ID: f2a3b4c5d6e7
Revises: e1d2c3b4a5f6
Create Date: 2026-08-15 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1d2c3b4a5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Enhance nodes table with management fields ──────────────────────
    op.add_column("nodes", sa.Column("usage_status", sa.String(length=16), nullable=False, server_default="online"))
    op.add_column("nodes", sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True))
    op.add_column("nodes", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.add_column("nodes", sa.Column("city", sa.String(length=64), nullable=True))
    op.add_column("nodes", sa.Column("max_users", sa.Integer, nullable=True))
    op.add_column("nodes", sa.Column("current_users", sa.Integer, nullable=False, server_default="0"))
    op.add_column("nodes", sa.Column("tags", sa.JSON, nullable=True))
    op.add_column("nodes", sa.Column("note", sa.Text, nullable=True))
    op.add_column(
        "nodes",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── admin_nodes: which admins can see / manage which nodes ──────────
    # New nodes are auto-assigned to ALL existing admins by default.
    # Sudo admins can later uncheck (revoke) access per sub-admin.
    op.create_table(
        "admin_nodes",
        sa.Column(
            "admin_id",
            sa.Integer,
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "node_id",
            sa.Integer,
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_admin_nodes_admin_id", "admin_nodes", ["admin_id"])
    op.create_index("ix_admin_nodes_node_id", "admin_nodes", ["node_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_nodes_node_id", table_name="admin_nodes")
    op.drop_index("ix_admin_nodes_admin_id", table_name="admin_nodes")
    op.drop_table("admin_nodes")

    op.drop_column("nodes", "updated_at")
    op.drop_column("nodes", "note")
    op.drop_column("nodes", "tags")
    op.drop_column("nodes", "current_users")
    op.drop_column("nodes", "max_users")
    op.drop_column("nodes", "city")
    op.drop_column("nodes", "country_code")
    op.drop_column("nodes", "last_health_check")
    op.drop_column("nodes", "usage_status")

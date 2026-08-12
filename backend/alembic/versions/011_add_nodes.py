"""add_nodes

Revision ID: d9e8f7a6b5c4
Revises: c8d7e6f5a4b3
Create Date: 2026-08-12 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e8f7a6b5c4"
down_revision: str | Sequence[str] | None = "c8d7e6f5a4b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nodes — future feature: attach nodes to users (accessible via
    # subscription). Schema-only for now; routing not implemented yet.
    op.create_table(
        "nodes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), unique=True, nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer, nullable=False, server_default="1194"),
        sa.Column("protocol", sa.String(length=16), nullable=False, server_default="udp"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Many-to-many association: user <-> node.
    op.create_table(
        "user_nodes",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("node_id", sa.Integer, sa.ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("user_nodes")
    op.drop_table("nodes")

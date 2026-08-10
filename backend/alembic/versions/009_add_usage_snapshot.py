"""add_usage_snapshot

Revision ID: b7c6d5e4f3a2
Revises: a6b5c4d3e2f1
Create Date: 2026-08-11 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7c6d5e4f3a2'
down_revision: str | Sequence[str] | None = 'a6b5c4d3e2f1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Per-user session byte-counter snapshot for the usage-sync job.
    # Persisted so the baseline survives disconnects and backend restarts.
    op.add_column('users', sa.Column('last_rx', sa.Integer, nullable=True, default=None))
    op.add_column('users', sa.Column('last_tx', sa.Integer, nullable=True, default=None))
    op.add_column('users', sa.Column('last_connected_since', sa.String(length=64), nullable=True, default=None))


def downgrade() -> None:
    op.drop_column('users', 'last_connected_since')
    op.drop_column('users', 'last_tx')
    op.drop_column('users', 'last_rx')

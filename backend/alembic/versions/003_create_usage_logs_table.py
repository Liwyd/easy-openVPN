"""create_usage_logs_table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-08 00:00:02.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: str | Sequence[str] | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the usage_logs table — traffic snapshots for graphing.

    NOTE: This table will grow fast. A retention/cleanup job will be needed
    to prune entries older than 30 days by default (configurable via the
    USAGE_LOG_RETENTION_DAYS env var). The cleanup job is implemented in
    a later stage.
    """
    op.create_table(
        'usage_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('bytes_sent', sa.BigInteger(), nullable=False),
        sa.Column('bytes_received', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'timestamp', name='uq_user_timestamp'),
    )
    op.create_index('ix_usage_logs_user_id', 'usage_logs', ['user_id'], unique=False)
    op.create_index('ix_usage_logs_user_id_timestamp', 'usage_logs', ['user_id', 'timestamp'], unique=False)


def downgrade() -> None:
    """Drop the usage_logs table."""
    op.drop_index('ix_usage_logs_user_id_timestamp', table_name='usage_logs')
    op.drop_index('ix_usage_logs_user_id', table_name='usage_logs')
    op.drop_table('usage_logs')

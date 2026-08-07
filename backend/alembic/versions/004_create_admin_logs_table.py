"""create_admin_logs_table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-08 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the admin_logs table — audit trail for admin actions."""
    op.create_table(
        'admin_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.Enum('CREATE_USER', 'UPDATE_USER', 'DELETE_USER', 'DISABLE_USER', 'ENABLE_USER', 'CREATE_ADMIN', 'UPDATE_ADMIN', 'DELETE_ADMIN', 'RESET_USAGE', 'REGENERATE_SUBSCRIPTION', 'UPDATE_SERVER_CONFIG', name='adminaction', native_enum=False), nullable=False),
        sa.Column('target_type', sa.Enum('USER', 'ADMIN', 'SERVER_CONFIG', name='targettype', native_enum=False), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_admin_logs_admin_id', 'admin_logs', ['admin_id'], unique=False)
    op.create_index('ix_admin_logs_admin_id_timestamp', 'admin_logs', ['admin_id', 'timestamp'], unique=False)


def downgrade() -> None:
    """Drop the admin_logs table."""
    op.drop_index('ix_admin_logs_admin_id_timestamp', table_name='admin_logs')
    op.drop_index('ix_admin_logs_admin_id', table_name='admin_logs')
    op.drop_table('admin_logs')

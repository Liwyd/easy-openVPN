"""create_users_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-08 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the users (VPN client) table."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'DISABLED', 'EXPIRED', 'LIMITED', name='userstatus', native_enum=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('data_limit', sa.Integer(), nullable=True),
        sa.Column('data_used', sa.Integer(), nullable=False),
        sa.Column('data_limit_reset_strategy', sa.Enum('NO_RESET', 'DAILY', 'WEEKLY', 'MONTHLY', name='datalimitresetstrategy', native_enum=False), nullable=False),
        sa.Column('expire_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('time_window_start', sa.Time(), nullable=True),
        sa.Column('time_window_end', sa.Time(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('cert_serial', sa.String(length=64), nullable=True),
        sa.Column('common_name', sa.String(length=128), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('subscription_token', sa.String(length=64), nullable=False),
        sa.Column('subscription_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_reset_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_subscription_token', 'users', ['subscription_token'], unique=True)
    op.create_index('ix_users_admin_id', 'users', ['admin_id'], unique=False)
    op.create_index('ix_users_expire_at', 'users', ['expire_at'], unique=False)
    op.create_index('ix_users_status', 'users', ['status'], unique=False)


def downgrade() -> None:
    """Drop the users table."""
    op.drop_index('ix_users_status', table_name='users')
    op.drop_index('ix_users_expire_at', table_name='users')
    op.drop_index('ix_users_admin_id', table_name='users')
    op.drop_index('ix_users_subscription_token', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')

"""create_admins_table

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-08 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the admins table — base of the admin hierarchy."""
    op.create_table(
        'admins',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('hashed_password', sa.String(length=128), nullable=False),
        sa.Column('is_sudo', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('disabled', sa.Boolean(), nullable=False),
        sa.Column('password_reset_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_limit', sa.Integer(), nullable=True),
        sa.Column('data_used', sa.Integer(), nullable=False),
        sa.Column('parent_admin_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['parent_admin_id'], ['admins.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_admins_username', 'admins', ['username'], unique=True)


def downgrade() -> None:
    """Drop the admins table."""
    op.drop_index('ix_admins_username', table_name='admins')
    op.drop_table('admins')

"""add_billing

Revision ID: a6b5c4d3e2f1
Revises: f1e2d3c4b5a6
Create Date: 2026-08-10 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a6b5c4d3e2f1'
down_revision: str | Sequence[str] | None = 'f1e2d3c4b5a6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add billing fields to admins table
    op.add_column('admins', sa.Column('price_per_user', sa.Float, nullable=True, default=None))
    op.add_column('admins', sa.Column('price_per_gb', sa.Float, nullable=True, default=None))
    op.add_column('admins', sa.Column('debt', sa.Float, nullable=False, server_default='0'))

    # Create billing_records table
    op.create_table(
        'billing_records',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('admin_id', sa.Integer, sa.ForeignKey('admins.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('billing_records')
    op.drop_column('admins', 'debt')
    op.drop_column('admins', 'price_per_gb')
    op.drop_column('admins', 'price_per_user')

"""create_jwt_table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-08 00:00:05.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the jwt table — single-row HMAC signing key for JWT tokens."""
    op.create_table(
        'jwt',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('secret_key', sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Drop the jwt table."""
    op.drop_table('jwt')

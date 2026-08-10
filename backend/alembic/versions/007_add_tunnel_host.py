"""add_tunnel_host_to_server_config

Revision ID: f1e2d3c4b5a6
Revises: f6a7b8c9d0e1
Create Date: 2026-08-10 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: str | Sequence[str] | None = 'f6a7b8c9d0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add tunnel_host — optional address that forwards to this server.

    When set, generated .ovpn configs use it as the `remote` endpoint
    instead of public_host. Exists purely for client configs; the
    OpenVPN server itself is untouched.
    """
    op.add_column('server_config', sa.Column('tunnel_host', sa.String(length=255), nullable=False, server_default=''))


def downgrade() -> None:
    """Drop the tunnel_host column."""
    op.drop_column('server_config', 'tunnel_host')

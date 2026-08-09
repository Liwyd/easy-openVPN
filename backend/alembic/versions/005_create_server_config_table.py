"""create_server_config_table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-08 00:00:04.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: str | Sequence[str] | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the server_config table — single-row OpenVPN server settings.

    NOTE: Changing protocol/port/cipher on a live server requires
    regenerating ALL client configs and restarting OpenVPN. That
    orchestration happens in vpn-core/backend in a later stage — this
    stage is schema only.
    """
    op.create_table(
        'server_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('protocol', sa.Enum('UDP', 'TCP', name='protocol', native_enum=False), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('interface', sa.String(length=16), nullable=False),
        sa.Column('cipher', sa.Enum('AES_256_GCM', 'AES_128_GCM', 'CHACHA20_POLY1305',
                                    name='cipher', native_enum=False), nullable=False),
        sa.Column('auth_digest', sa.Enum('SHA256', 'SHA512',
                                         name='authdigest', native_enum=False), nullable=False),
        sa.Column('tls_mode', sa.Enum('TLS_CRYPT', 'TLS_AUTH', 'NONE',
                                      name='tlssettings', native_enum=False), nullable=False),
        sa.Column('dns_preset', sa.Enum('CLOUDFLARE', 'GOOGLE', 'ADGUARD', 'CUSTOM',
                                        name='dnspreset', native_enum=False), nullable=False),
        sa.Column('dns_servers', sa.JSON(), nullable=True),
        sa.Column('mtu', sa.Integer(), nullable=True),
        sa.Column('keepalive_interval', sa.Integer(), nullable=False),
        sa.Column('keepalive_timeout', sa.Integer(), nullable=False),
        sa.Column('client_to_client', sa.Boolean(), nullable=False),
        sa.Column('redirect_gateway', sa.Boolean(), nullable=False),
        sa.Column('public_host', sa.String(length=255), nullable=False),
        sa.Column('subscription_url_prefix', sa.String(length=255), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by_admin_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_admin_id'], ['admins.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Drop the server_config table."""
    op.drop_table('server_config')

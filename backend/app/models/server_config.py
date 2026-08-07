"""ServerConfig — single-row table holding OpenVPN server-wide settings.

This stores every setting the panel's Settings page exposes, so
operators don't have to SSH in to change the VPN itself. The vpn-core
module is responsible for rendering this row into the actual server.conf
file and triggering OpenVPN reload/restart.

NOTE: Changing protocol/port/cipher on a live server requires
regenerating ALL client configs and restarting OpenVPN. That
orchestration happens in vpn-core/backend in a later stage — this
stage is schema only.
"""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Protocol(str, enum.Enum):
    UDP = "udp"
    TCP = "tcp"


class Cipher(str, enum.Enum):
    AES_256_GCM = "AES-256-GCM"
    AES_128_GCM = "AES-128-GCM"
    CHACHA20_POLY1305 = "CHACHA20-POLY1305"


class AuthDigest(str, enum.Enum):
    SHA256 = "SHA256"
    SHA512 = "SHA512"


class TLSSettings(str, enum.Enum):
    TLS_CRYPT = "tls-crypt"
    TLS_AUTH = "tls-auth"
    NONE = "none"


class DNSPreset(str, enum.Enum):
    CLOUDFLARE = "cloudflare"
    GOOGLE = "google"
    ADGUARD = "adguard"
    CUSTOM = "custom"


class ServerConfig(Base):
    __tablename__ = "server_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Network settings
    protocol: Mapped[Protocol] = mapped_column(
        Enum(Protocol, native_enum=False), default=Protocol.UDP, nullable=False
    )
    port: Mapped[int] = mapped_column(Integer, default=1194, nullable=False)
    interface: Mapped[str] = mapped_column(String(16), default="tun0", nullable=False)

    # Cryptography
    cipher: Mapped[Cipher] = mapped_column(
        Enum(Cipher, native_enum=False), default=Cipher.AES_256_GCM, nullable=False
    )
    auth_digest: Mapped[AuthDigest] = mapped_column(
        Enum(AuthDigest, native_enum=False), default=AuthDigest.SHA256, nullable=False
    )
    tls_mode: Mapped[TLSSettings] = mapped_column(
        Enum(TLSSettings, native_enum=False), default=TLSSettings.TLS_CRYPT, nullable=False
    )

    # DNS
    dns_preset: Mapped[DNSPreset] = mapped_column(
        Enum(DNSPreset, native_enum=False), default=DNSPreset.CLOUDFLARE, nullable=False
    )
    dns_servers: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)

    # Connection tuning
    mtu: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    keepalive_interval: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    keepalive_timeout: Mapped[int] = mapped_column(Integer, default=120, nullable=False)

    # Client behavior
    client_to_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    redirect_gateway: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Public-facing host — domain or IP clients connect to; used when
    # rendering .ovpn files.
    public_host: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    # Subscription URL prefix — used to build the full /sub/{token} URL.
    # e.g. "https://panel.example.com"
    subscription_url_prefix: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    # Audit
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True, default=None
    )

    # Relationships
    updated_by_admin: Mapped[Admin | None] = relationship("Admin", lazy="select")

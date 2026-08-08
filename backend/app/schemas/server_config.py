"""Server config schemas — request/response models for server settings API."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.models.server_config import AuthDigest, Cipher, DNSPreset, Protocol, TLSSettings


class ServerConfigUpdate(BaseModel):
    protocol: Protocol | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    interface: str | None = None
    cipher: Cipher | None = None
    auth_digest: AuthDigest | None = None
    tls_mode: TLSSettings | None = None
    dns_preset: DNSPreset | None = None
    dns_servers: list[str] | None = None
    mtu: int | None = Field(default=None, ge=576, le=65535)
    keepalive_interval: int | None = Field(default=None, ge=1)
    keepalive_timeout: int | None = Field(default=None, ge=1)
    client_to_client: bool | None = None
    redirect_gateway: bool | None = None
    public_host: str | None = None
    subscription_url_prefix: str | None = None


class ServerConfigResponse(BaseModel):
    id: int
    protocol: Protocol
    port: int
    interface: str
    cipher: Cipher
    auth_digest: AuthDigest
    tls_mode: TLSSettings
    dns_preset: DNSPreset
    dns_servers: list | None
    mtu: int | None
    keepalive_interval: int
    keepalive_timeout: int
    client_to_client: bool
    redirect_gateway: bool
    public_host: str
    subscription_url_prefix: str
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class ServerConfigApplyResult(BaseModel):
    success: bool
    requires_redownload: bool
    requires_redownload_fields: list[str]
    message: str

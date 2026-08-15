"""Node schemas — request/response models for node CRUD and admin association."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, field_validator


class NodeCreate(BaseModel):
    name: str
    address: str
    port: int = 1194
    protocol: str = "udp"
    enabled: bool = True
    country_code: str | None = None
    city: str | None = None
    max_users: int | None = None
    tags: list[str] | None = None
    note: str | None = None

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Node name cannot be empty")
        if len(v) > 64:
            raise ValueError("Node name must be 64 characters or fewer")
        return v

    @field_validator("port")
    @classmethod
    def check_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("protocol")
    @classmethod
    def check_protocol(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("udp", "tcp"):
            raise ValueError("Protocol must be 'udp' or 'tcp'")
        return v


class NodeUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    port: int | None = None
    protocol: str | None = None
    enabled: bool | None = None
    country_code: str | None = None
    city: str | None = None
    max_users: int | None = None
    tags: list[str] | None = None
    note: str | None = None


class NodeResponse(BaseModel):
    id: int
    name: str
    address: str
    port: int
    protocol: str
    enabled: bool
    created_at: dt.datetime
    usage_status: str
    last_health_check: dt.datetime | None
    country_code: str | None
    city: str | None
    max_users: int | None
    current_users: int
    tags: list[str] | None
    note: str | None
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class NodeWithAdminsResponse(NodeResponse):
    admin_ids: list[int]


class AdminNodeAssign(BaseModel):
    """Request body to assign / revoke nodes for a specific admin."""
    node_ids: list[int]


class AdminNodesResponse(BaseModel):
    admin_id: int
    username: str
    node_ids: list[int]


class NodeAdminsResponse(BaseModel):
    node_id: int
    name: str
    admin_ids: list[int]

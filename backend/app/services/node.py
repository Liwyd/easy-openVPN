"""Node service — CRUD + admin-association helpers.

Core logic:
* When a node is created, it is auto-assigned to **all** existing admins.
* A sudo admin can later grant/revoke node access per sub-admin.
* Sub-admins only see nodes assigned to them via ``admin_nodes``.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.models.node import Node, admin_nodes

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auto-assign
# ---------------------------------------------------------------------------

def assign_node_to_all_admins(db: Session, node: Node) -> None:
    """Grant every existing admin access to *node*.

    Called right after a new node is created so no admin is left out.
    Sudo admins can later revoke access for individual sub-admins.
    """
    admins = db.query(Admin).all()
    for admin in admins:
        if admin not in node.admins:
            node.admins.append(admin)
    db.flush()


def sync_node_admins(db: Session, node: Node, admin_ids: list[int]) -> None:
    """Replace the admin-association list for *node* with *admin_ids*.

    Existing associations not in *admin_ids* are removed; new ones are
    added.  The node is always accessible to sudo admins (they are
    included implicitly and cannot be removed).
    """
    current_ids = {a.id for a in node.admins}
    target_ids = set(admin_ids)

    # Ensure all sudo admins are always included
    sudo_ids = {a.id for a in db.query(Admin).filter(Admin.is_sudo.is_(True)).all()}
    target_ids |= sudo_ids

    # Remove admins no longer in the list
    for admin in list(node.admins):
        if admin.id not in target_ids:
            node.admins.remove(admin)

    # Add new admins
    if target_ids - current_ids:
        new_admins = db.query(Admin).filter(Admin.id.in_(target_ids - current_ids)).all()
        for admin in new_admins:
            node.admins.append(admin)

    db.flush()


def set_admin_nodes(db: Session, admin: Admin, node_ids: list[int]) -> None:
    """Replace the node-association list for *admin* with *node_ids*.

    Used by sudo admins to control which nodes a sub-admin can manage.
    """
    current_ids = {n.id for n in admin.nodes}
    target_ids = set(node_ids)

    # Remove nodes no longer in the list
    for node in list(admin.nodes):
        if node.id not in target_ids:
            admin.nodes.remove(node)

    # Add new nodes
    if target_ids - current_ids:
        new_nodes = db.query(Node).filter(Node.id.in_(target_ids - current_ids)).all()
        for node in new_nodes:
            admin.nodes.append(node)

    db.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_admin_node_ids(admin: Admin) -> list[int]:
    """Return sorted node IDs the admin has access to."""
    return sorted(n.id for n in admin.nodes)


def get_node_admin_ids(node: Node) -> list[int]:
    """Return sorted admin IDs that have access to the node."""
    return sorted(a.id for a in node.admins)


def node_to_dict(node: Node) -> dict:
    """Serialize node tags from stored JSON text to a Python list."""
    d = {
        "id": node.id,
        "name": node.name,
        "address": node.address,
        "port": node.port,
        "protocol": node.protocol,
        "enabled": node.enabled,
        "created_at": node.created_at,
        "usage_status": node.usage_status,
        "last_health_check": node.last_health_check,
        "country_code": node.country_code,
        "city": node.city,
        "max_users": node.max_users,
        "current_users": node.current_users,
        "tags": _parse_tags(node.tags),
        "note": node.note,
        "updated_at": node.updated_at,
    }
    return d


def _parse_tags(raw: str | list | None) -> list[str]:
    """Normalize tags stored as JSON text or already a list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []

"""Node CRUD router — sudo-only node management with admin-association control.

Endpoints:
* CRUD for nodes (sudo only)
* Assign/revoke nodes per admin (sudo only)
* List nodes visible to the current admin (any admin)
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.bot.events import EventCategory, emit
from app.db import get_db
from app.models.admin import Admin
from app.models.admin_log import AdminAction, TargetType
from app.models.node import Node
from app.schemas.node import (
    AdminNodeAssign,
    AdminNodesResponse,
    NodeAdminsResponse,
    NodeCreate,
    NodeResponse,
    NodeUpdate,
    NodeWithAdminsResponse,
)
from app.services.auth import get_current_admin, get_current_sudo_admin
from app.services.node import (
    assign_node_to_all_admins,
    get_node_admin_ids,
    node_to_dict,
    set_admin_nodes,
    sync_node_admins,
)
from app.services.quota import write_admin_log

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


# ── Helpers ──────────────────────────────────────────────────────────────

def _tags_to_json(tags: list[str] | None) -> str | None:
    """Serialize tags list to JSON text for storage."""
    if tags is None:
        return None
    return json.dumps(tags)


def _node_response(node: Node) -> NodeResponse:
    """Build a NodeResponse from a Node model instance."""
    return NodeResponse(**node_to_dict(node))


def _node_with_admins_response(node: Node) -> NodeWithAdminsResponse:
    """Build a NodeWithAdminsResponse including assigned admin IDs."""
    return NodeWithAdminsResponse(
        **node_to_dict(node),
        admin_ids=get_node_admin_ids(node),
    )


# ── Node CRUD (sudo only) ──────────────────────────────────────────────

@router.post("", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
def create_node(
    body: NodeCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Create a new node and auto-assign it to all existing admins."""
    if db.query(Node).filter(Node.name == body.name).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Node name already taken",
        )

    node = Node(
        name=body.name,
        address=body.address,
        port=body.port,
        protocol=body.protocol,
        enabled=body.enabled,
        country_code=body.country_code,
        city=body.city,
        max_users=body.max_users,
        tags=_tags_to_json(body.tags),
        note=body.note,
    )
    db.add(node)
    db.flush()

    # Auto-assign to all existing admins
    assign_node_to_all_admins(db, node)

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.CREATE_NODE,
        target_type=TargetType.NODE,
        target_id=node.id,
        detail=f"Created node '{body.name}' ({body.address}:{body.port})",
    )
    db.commit()
    db.refresh(node)

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="node_created",
        username=node.name,
        admin_username=current_admin.username,
    )

    return _node_response(node)


@router.get("", response_model=list[NodeWithAdminsResponse])
def list_nodes(
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    name: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """List nodes visible to the current admin.

    Sudo admins see all nodes.  Sub-admins see only nodes assigned to them.
    """
    if current_admin.is_sudo:
        q = db.query(Node)
    else:
        q = db.query(Node).filter(Node.admins.any(Admin.id == current_admin.id))

    if name:
        q = q.filter(Node.name.ilike(f"%{name}%"))
    if enabled is not None:
        q = q.filter(Node.enabled == enabled)

    total = q.count()
    response.headers["X-Total-Count"] = str(total)

    nodes = q.order_by(Node.id).offset(offset).limit(limit).all()
    return [_node_with_admins_response(n) for n in nodes]


@router.get("/{node_id}", response_model=NodeWithAdminsResponse)
def get_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Get a specific node.  Sub-admins can only view nodes assigned to them."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    if not current_admin.is_sudo:
        if not any(a.id == current_admin.id for a in node.admins):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    return _node_with_admins_response(node)


@router.put("/{node_id}", response_model=NodeResponse)
def update_node(
    node_id: int,
    body: NodeUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Update a node (sudo only)."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    if body.name is not None and body.name != node.name:
        if db.query(Node).filter(Node.name == body.name, Node.id != node_id).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Node name already taken",
            )
        node.name = body.name

    if body.address is not None:
        node.address = body.address
    if body.port is not None:
        node.port = body.port
    if body.protocol is not None:
        node.protocol = body.protocol.lower()
    if body.enabled is not None:
        node.enabled = body.enabled
    if body.country_code is not None:
        node.country_code = body.country_code
    if body.city is not None:
        node.city = body.city
    if body.max_users is not None:
        node.max_users = body.max_users
    if body.tags is not None:
        node.tags = _tags_to_json(body.tags)
    if body.note is not None:
        node.note = body.note

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.UPDATE_NODE,
        target_type=TargetType.NODE,
        target_id=node.id,
        detail=f"Updated node '{node.name}'",
    )
    db.commit()
    db.refresh(node)

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="node_updated",
        username=node.name,
        admin_username=current_admin.username,
    )

    return _node_response(node)


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Delete a node (sudo only).  Removes all admin and user associations."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.DELETE_NODE,
        target_type=TargetType.NODE,
        target_id=node.id,
        detail=f"Deleted node '{node.name}'",
    )
    db.delete(node)
    db.commit()

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="node_deleted",
        username=node.name,
        admin_username=current_admin.username,
    )


# ── Admin-Node association management (sudo only) ──────────────────────

@router.get("/{node_id}/admins", response_model=NodeAdminsResponse)
def get_node_admins(
    node_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """List admin IDs that have access to this node."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    return NodeAdminsResponse(
        node_id=node.id,
        name=node.name,
        admin_ids=get_node_admin_ids(node),
    )


@router.put("/{node_id}/admins", response_model=NodeAdminsResponse)
def set_node_admins(
    node_id: int,
    body: AdminNodeAssign,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Set which admins have access to this node.

    Sudo admins are always included and cannot be removed.
    Pass the full list of admin_ids that should have access.
    """
    node = db.query(Node).filter(Node.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    sync_node_admins(db, node, body.node_ids)

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.ASSIGN_NODE_ADMIN,
        target_type=TargetType.NODE,
        target_id=node.id,
        detail=f"Updated admin access for node '{node.name}'",
    )
    db.commit()
    db.refresh(node)

    return NodeAdminsResponse(
        node_id=node.id,
        name=node.name,
        admin_ids=get_node_admin_ids(node),
    )


# ── Per-admin node assignment (sudo only) ──────────────────────────────

@router.get("/admin/{admin_id}", response_model=AdminNodesResponse)
def get_admin_nodes(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """List node IDs assigned to a specific admin."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    from app.services.node import get_admin_node_ids

    return AdminNodesResponse(
        admin_id=admin.id,
        username=admin.username,
        node_ids=get_admin_node_ids(admin),
    )


@router.put("/admin/{admin_id}", response_model=AdminNodesResponse)
def update_admin_nodes(
    admin_id: int,
    body: AdminNodeAssign,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Set which nodes a specific admin can access.

    Pass the full list of node_ids the admin should see.
    """
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    set_admin_nodes(db, admin, body.node_ids)

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.ASSIGN_NODE_ADMIN,
        target_type=TargetType.ADMIN,
        target_id=admin.id,
        detail=f"Updated node access for admin '{admin.username}'",
    )
    db.commit()
    db.refresh(admin)

    from app.services.node import get_admin_node_ids

    return AdminNodesResponse(
        admin_id=admin.id,
        username=admin.username,
        node_ids=get_admin_node_ids(admin),
    )

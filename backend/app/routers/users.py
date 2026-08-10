"""User CRUD router — quota-aware user management wired to vpn-core.

Every operation is ownership-aware: sub-admins can only manage their own
users; sudo admins can manage anyone's users.  Quota validation is
enforced at creation time using the allocation-based guard from
``app.services.quota``.

Soft-delete policy: DELETE sets status='disabled' and revoked=True but
keeps the DB row for history (mirrors Marzban's approach).  Revoked
users are excluded from list queries by default.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.bot.events import EventCategory, emit
from app.config import (
    EASYRSA_DIR,
    OPENVPN_MANAGEMENT_SOCKET,
)
from app.db import get_db
from app.logging_config import enforcement_log
from app.models.admin import Admin
from app.models.admin_log import AdminAction, TargetType
from app.models.server_config import ServerConfig
from app.models.user import User, UserStatus
from app.schemas.user import (
    SubscriptionURLResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.auth import get_current_admin
from app.services.quota import (
    can_admin_allocate,
    recalculate_admin_data_used,
    write_admin_log,
)
from app.services.vpn_bridge import (
    create_client_cert as _create_client_cert,
)
from app.services.vpn_bridge import (
    disable_client as _disable_client,
)
from app.services.vpn_bridge import (
    enable_client as _enable_client,
)
from app.services.vpn_bridge import (
    generate_ovpn_file as _generate_ovpn_file,
)
from app.services.vpn_bridge import (
    kill_client_session as _kill_client_session,
)
from app.services.vpn_bridge import (
    resolve_client_host as _resolve_client_host,
)
from app.services.vpn_bridge import (
    revoke_client_cert as _revoke_client_cert,
)

router = APIRouter(prefix="/api/users", tags=["users"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_validated_user(
    username: str,
    admin: Admin,
    db: Session,
) -> User:
    """Fetch user by username, enforce ownership.

    Sub-admins can only see their own users; sudo admins see all.
    Returns 404 (not 403) for unauthorized access to avoid leaking
    user existence.
    """
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not admin.is_sudo and user.admin_id != admin.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _get_server_settings(db: Session) -> ServerConfig:
    """Get the server config row (creates default if missing)."""
    cfg = db.query(ServerConfig).first()
    if cfg is None:
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db)
        db.flush()
        cfg = db.query(ServerConfig).first()
    return cfg


def _render_ovpn_for_user(user: User, db: Session) -> str:
    """Render the .ovpn file content for a user."""
    cfg = _get_server_settings(db)
    return _generate_ovpn_file(
        common_name=user.common_name or user.username,
        server_dir="/etc/openvpn/server",
        public_ip=_resolve_client_host(cfg.public_host, cfg.tunnel_host),
        protocol=cfg.protocol.value,
        port=cfg.port,
    )


# ---------------------------------------------------------------------------
# POST /api/users — create user
# ---------------------------------------------------------------------------

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Create a VPN user.  Quota-aware: validates admin has enough
    remaining allocatable quota to cover the user's data_limit.

    Certificate creation happens first; the DB row is only persisted
    if cert generation succeeds.  On cert failure the error is returned
    cleanly — no orphaned certs without DB rows.
    """
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    # Quota check: allocation-based guard.
    user_data_limit = body.data_limit or 0
    if user_data_limit > 0:
        if not can_admin_allocate(current_admin, user_data_limit, db):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Creating this user would exceed your quota",
            )

    # Create the certificate FIRST — if this fails, nothing is written to DB.
    try:
        cfg = _get_server_settings(db)
        _create_client_cert(
            common_name=body.username,
            server_dir="/etc/openvpn/server",
            easyrsa_dir=EASYRSA_DIR,
            public_ip=_resolve_client_host(cfg.public_host, cfg.tunnel_host),
            protocol=cfg.protocol.value,
            port=cfg.port,
        )
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate already exists for this username",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create certificate: {exc}",
        ) from exc

    # Cert creation succeeded — now persist the DB row.
    new_user = User(
        username=body.username,
        admin_id=current_admin.id,
        data_limit=body.data_limit,
        data_used=0,
        expire_at=body.expire_at,
        time_window_start=body.time_window_start,
        time_window_end=body.time_window_end,
        note=body.note,
        common_name=body.username,
        revoked=False,
    )

    db.add(new_user)
    db.flush()

    # Update admin data_used (allocation tracking).
    recalculate_admin_data_used(current_admin, db)

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.CREATE_USER,
        target_type=TargetType.USER,
        target_id=new_user.id,
        detail=f"Created user '{body.username}'",
    )
    db.commit()
    db.refresh(new_user)

    from app.bot.formatter import _fmt_bytes

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="user_created",
        username=body.username,
        admin_username=current_admin.username,
        data_limit=body.data_limit,
        data_limit_str=_fmt_bytes(body.data_limit) if body.data_limit else None,
        expires=body.expire_at.isoformat() if body.expire_at else None,
    )

    return new_user


# ---------------------------------------------------------------------------
# GET /api/users — list users
# ---------------------------------------------------------------------------

@router.get("", response_model=list[UserResponse])
def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    username: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """List users.  Sub-admins see only their own; sudo sees all.
    Excludes soft-deleted users (revoked=True) by default.
    """
    q = db.query(User).filter(User.revoked.is_(False))
    if username:
        q = q.filter(User.username.ilike(f"%{username}%"))
    if not current_admin.is_sudo:
        q = q.filter(User.admin_id == current_admin.id)
    return q.order_by(User.id).offset(offset).limit(limit).all()


# ---------------------------------------------------------------------------
# GET /api/users/{username} — get user
# ---------------------------------------------------------------------------

@router.get("/{username}", response_model=UserResponse)
def get_user(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Get a specific user by username.  Ownership enforced."""
    return _get_validated_user(username, current_admin, db)


# ---------------------------------------------------------------------------
# GET /api/users/{username}/config — download .ovpn file
# ---------------------------------------------------------------------------

@router.get("/{username}/config")
def get_user_config(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Return the .ovpn file for download.  Auth + ownership required."""
    user = _get_validated_user(username, current_admin, db)
    if user.revoked:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="User certificate has been revoked")

    ovpn_content = _render_ovpn_for_user(user, db)
    return Response(
        content=ovpn_content,
        media_type="application/x-openvpn-profile",
        headers={
            "Content-Disposition": f'attachment; filename="{user.username}.ovpn"',
        },
    )


# ---------------------------------------------------------------------------
# PUT /api/users/{username} — update user
# ---------------------------------------------------------------------------

@router.put("/{username}", response_model=UserResponse)
def update_user(
    username: str,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Update a user's settings.  Ownership enforced.
    If changing data_limit, validates the new limit against admin's remaining quota.
    """
    user = _get_validated_user(username, current_admin, db)
    old_status = user.status

    if body.data_limit is not None:
        # If increasing the user's data_limit, validate admin quota.
        old_limit = user.data_limit or 0
        new_limit = body.data_limit
        delta = new_limit - old_limit
        if delta > 0 and not can_admin_allocate(current_admin, delta, db):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Increasing this user's limit would exceed your quota",
            )
        user.data_limit = body.data_limit

    if body.expire_at is not None:
        user.expire_at = body.expire_at
    if body.time_window_start is not None:
        user.time_window_start = body.time_window_start
    if body.time_window_end is not None:
        user.time_window_end = body.time_window_end
    if body.note is not None:
        user.note = body.note
    if body.status is not None:
        user.status = body.status

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.UPDATE_USER,
        target_type=TargetType.USER,
        target_id=user.id,
        detail=f"Updated user '{username}'",
    )

    # Recalculate admin allocation.
    recalculate_admin_data_used(current_admin, db)

    db.commit()
    db.refresh(user)

    if body.status is not None and body.status != old_status:
        if body.status.value == "disabled":
            action = "user_disabled_admin"
        elif body.status.value == "active":
            action = "user_enabled"
        else:
            action = "user_updated"
    else:
        action = "user_updated"

    from app.bot.formatter import _fmt_bytes

    emit(
        category=EventCategory.ADMIN_ACTION,
        action=action,
        username=username,
        admin_username=current_admin.username,
        data_limit=user.data_limit,
        data_limit_str=_fmt_bytes(user.data_limit) if user.data_limit else None,
    )

    return user


# ---------------------------------------------------------------------------
# POST /api/users/{username}/disable — disable user
# ---------------------------------------------------------------------------

@router.post("/{username}/disable", response_model=UserResponse)
def disable_user(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Disable a user — kills active session and prevents reconnection."""
    user = _get_validated_user(username, current_admin, db)

    if user.status == UserStatus.DISABLED:
        return user

    if user.common_name:
        _kill_client_session(user.common_name, OPENVPN_MANAGEMENT_SOCKET)
        _disable_client(user.common_name, management_socket=OPENVPN_MANAGEMENT_SOCKET)

    user.status = UserStatus.DISABLED

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.DISABLE_USER,
        target_type=TargetType.USER,
        target_id=user.id,
        detail=f"Disabled user '{username}'",
    )

    enforcement_log(
        event="user_disabled",
        username=username,
        admin_username=current_admin.username,
        reason="manual",
    )

    db.commit()
    db.refresh(user)

    emit(
        category=EventCategory.ENFORCEMENT if user.common_name else EventCategory.ADMIN_ACTION,
        action="user_disabled_admin",
        username=username,
        admin_username=current_admin.username,
    )

    return user


# ---------------------------------------------------------------------------
# POST /api/users/{username}/enable — enable user
# ---------------------------------------------------------------------------

@router.post("/{username}/enable", response_model=UserResponse)
def enable_user(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Re-enable a disabled user."""
    user = _get_validated_user(username, current_admin, db)

    if user.status == UserStatus.ACTIVE:
        return user

    if user.common_name:
        _enable_client(user.common_name)

    user.status = UserStatus.ACTIVE

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.ENABLE_USER,
        target_type=TargetType.USER,
        target_id=user.id,
        detail=f"Enabled user '{username}'",
    )

    enforcement_log(
        event="user_enabled",
        username=username,
        admin_username=current_admin.username,
        reason="manual",
    )

    db.commit()
    db.refresh(user)

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="user_enabled",
        username=username,
        admin_username=current_admin.username,
    )

    return user


# ---------------------------------------------------------------------------
# DELETE /api/users/{username} — soft-delete (revoke + disable)
# ---------------------------------------------------------------------------

@router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Soft-delete a user: revoke cert, disable, keep DB row for history.

    The row stays in DB with status='disabled' and revoked=True, but is
    excluded from list queries by default (see list_users).
    Recalculates admin's data_used in the same transaction.
    """
    user = _get_validated_user(username, current_admin, db)

    # Revoke the certificate via vpn-core
    if user.common_name and not user.revoked:
        try:
            _kill_client_session(user.common_name, OPENVPN_MANAGEMENT_SOCKET)
            _revoke_client_cert(user.common_name)
        except Exception:
            # Best-effort revocation — log but don't block DB cleanup
            enforcement_log(
                event="cert_revoke_failed",
                username=username,
                admin_username=current_admin.username,
                reason="vpn-core error",
            )

    user.status = UserStatus.DISABLED
    user.revoked = True

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.DELETE_USER,
        target_type=TargetType.USER,
        target_id=user.id,
        detail=f"Deleted user '{username}'",
    )

    # Recalculate admin data_used after deletion.
    admin = db.query(Admin).filter(Admin.id == user.admin_id).first()
    if admin is not None:
        recalculate_admin_data_used(admin, db)

    enforcement_log(
        event="user_deleted",
        username=username,
        admin_username=current_admin.username,
        reason="admin_action",
    )

    db.commit()

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="user_deleted",
        username=username,
        admin_username=current_admin.username,
    )


# ---------------------------------------------------------------------------
# POST /api/users/{username}/reset-usage — zero out data_used
# ---------------------------------------------------------------------------

@router.post("/{username}/reset-usage", response_model=UserResponse)
def reset_usage(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Reset a user's data_used to zero and recalculate admin data_used."""
    user = _get_validated_user(username, current_admin, db)

    user.data_used = 0

    recalculate_admin_data_used(current_admin, db)

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.RESET_USAGE,
        target_type=TargetType.USER,
        target_id=user.id,
        detail=f"Reset usage for user '{username}'",
    )

    enforcement_log(
        event="usage_reset",
        username=username,
        admin_username=current_admin.username,
    )

    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# POST /api/users/{username}/subscription/revoke — regenerate token
# ---------------------------------------------------------------------------

@router.post("/{username}/subscription/revoke", response_model=UserResponse)
def revoke_subscription(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Regenerate subscription_token — invalidates the old public link
    immediately by updating subscription_updated_at.
    """
    import datetime as _dt

    user = _get_validated_user(username, current_admin, db)

    user.subscription_token = secrets.token_urlsafe(32)
    user.subscription_updated_at = _dt.datetime.now(_dt.UTC)

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.REGENERATE_SUBSCRIPTION,
        target_type=TargetType.USER,
        target_id=user.id,
        detail=f"Revoked subscription for user '{username}'",
    )

    enforcement_log(
        event="subscription_revoked",
        username=username,
        admin_username=current_admin.username,
    )

    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# GET /api/users/{username}/subscription-url — get the full URL
# ---------------------------------------------------------------------------

@router.get("/{username}/subscription-url", response_model=SubscriptionURLResponse)
def get_subscription_url(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Return the full absolute subscription URL for a user.
    Sudo/owning-admin-only.  Uses ServerConfig's subscription_url_prefix when
    configured; otherwise derives it from the incoming request so the link
    matches whatever host:port the panel is served on (Marzban-style).
    """
    user = _get_validated_user(username, current_admin, db)
    cfg = _get_server_settings(db)

    if cfg.subscription_url_prefix:
        prefix = cfg.subscription_url_prefix.rstrip("/")
    else:
        # No explicit prefix — build from the Host header so the subscription
        # page lives on the same host:port as the panel (nginx forwards the
        # real Host + X-Forwarded-Port).
        host = request.headers.get("host", request.url.hostname or "")
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        forwarded_port = request.headers.get("x-forwarded-port")
        if forwarded_port and forwarded_port not in ("80", "443"):
            base = f"{scheme}://{host.split(':')[0]}:{forwarded_port}"
        else:
            base = f"{scheme}://{host}"
        prefix = base

    url = f"{prefix}/sub/{user.subscription_token}"
    return SubscriptionURLResponse(subscription_url=url)

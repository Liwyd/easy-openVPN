"""User CRUD router — quota-aware user management.

Every operation is ownership-aware: sub-admins can only manage their own
users; sudo admins can manage anyone's users.  Quota validation is
enforced at creation time using the allocation-based guard from
``app.services.quota``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.admin import Admin
from app.models.admin_log import AdminAction, TargetType
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.auth import get_current_admin
from app.services.quota import (
    can_admin_allocate,
    recalculate_admin_data_used,
    write_admin_log,
)

router = APIRouter(prefix="/api/users", tags=["users"])


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


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Create a VPN user.  Quota-aware: validates admin has enough
    remaining allocatable quota to cover the user's data_limit.
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

    new_user = User(
        username=body.username,
        admin_id=current_admin.id,
        data_limit=body.data_limit,
        data_used=0,
        expire_at=body.expire_at,
        time_window_start=body.time_window_start,
        time_window_end=body.time_window_end,
        note=body.note,
    )

    # TODO: call vpn_core.create_client_cert(username) here to generate
    # the actual OpenVPN client certificate via easy-rsa.  For now the
    # cert fields remain None — the cert step is stubbed.
    # from vpn_core import create_client_cert
    # cert_serial, common_name = create_client_cert(body.username)
    # new_user.cert_serial = cert_serial
    # new_user.common_name = common_name

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
    return new_user


@router.get("", response_model=list[UserResponse])
def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    username: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """List users.  Sub-admins see only their own; sudo sees all."""
    q = db.query(User)
    if username:
        q = q.filter(User.username.ilike(f"%{username}%"))
    if not current_admin.is_sudo:
        q = q.filter(User.admin_id == current_admin.id)
    return q.order_by(User.id).offset(offset).limit(limit).all()


@router.get("/{username}", response_model=UserResponse)
def get_user(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Get a specific user by username.  Ownership enforced."""
    return _get_validated_user(username, current_admin, db)


@router.put("/{username}", response_model=UserResponse)
def update_user(
    username: str,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Update a user's settings.  Ownership enforced."""
    user = _get_validated_user(username, current_admin, db)

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
    return user


@router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Delete a user.  Ownership enforced.  Removes user and recalculates
    admin's data_used, all in one transaction.
    """
    user = _get_validated_user(username, current_admin, db)

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.DELETE_USER,
        target_type=TargetType.USER,
        target_id=user.id,
        detail=f"Deleted user '{username}'",
    )

    # TODO: call vpn_core.revoke_client_cert(user.common_name) here
    # to revoke the OpenVPN certificate before deleting the DB row.
    # from vpn_core import revoke_client_cert
    # if user.common_name:
    #     revoke_client_cert(user.common_name)

    admin = db.query(Admin).filter(Admin.id == user.admin_id).first()
    db.delete(user)

    # Recalculate admin data_used after deletion.
    if admin is not None:
        recalculate_admin_data_used(admin, db)

    db.commit()

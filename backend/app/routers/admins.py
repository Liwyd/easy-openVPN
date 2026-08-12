"""Admin CRUD router — sudo-only admin management with quota validation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.bot.events import EventCategory, emit
from app.db import get_db
from app.models.admin import Admin
from app.models.admin_log import AdminAction, TargetType
from app.models.user import User
from app.schemas.admin import AdminCreate, AdminResponse, AdminUpdate, AdminUsageResponse, AdminWithStatsResponse
from app.services.auth import get_current_sudo_admin
from app.services.quota import (
    can_admin_allocate,
    remaining_allocatable,
    write_admin_log,
)
from app.utils.password import hash_password

router = APIRouter(prefix="/api/admins", tags=["admins"])


@router.post("", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    body: AdminCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Create a sub-admin.  Only sudo admins can create admins.

    A data_limit is OPTIONAL: when omitted the sub-admin gets unlimited
    data.  When a limit is set, the creating sudo admin's remaining
    allocatable quota is validated to ensure the parent can cover the
    child's limit.
    """
    if db.query(Admin).filter(Admin.username == body.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    data_limit = body.data_limit

    # Validate parent admin has enough remaining quota
    if data_limit is not None and data_limit > 0:
        if not can_admin_allocate(current_admin, data_limit, db):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Creating this admin would exceed your quota",
            )

    new_admin = Admin(
        username=body.username,
        hashed_password=hash_password(body.password),
        is_sudo=body.is_sudo,
        disabled=False,
        data_limit=data_limit if not body.is_sudo else None,
        data_used=0,
        parent_admin_id=current_admin.id,
    )
    db.add(new_admin)
    db.flush()

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.CREATE_ADMIN,
        target_type=TargetType.ADMIN,
        target_id=new_admin.id,
        detail=f"Created admin '{body.username}'",
    )
    db.commit()
    db.refresh(new_admin)

    from app.bot.formatter import _fmt_bytes

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="admin_created",
        username=body.username,
        admin_username=current_admin.username,
        belongs_to=current_admin.username,
        data_limit=data_limit,
        data_limit_str=_fmt_bytes(data_limit) if data_limit else None,
    )

    return new_admin


@router.get("", response_model=list[AdminWithStatsResponse])
def list_admins(
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    username: str | None = Query(default=None),
    parent_admin_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """List admins with user stats. Only sudo admins can list admins."""
    q = db.query(Admin)
    if username:
        q = q.filter(Admin.username.ilike(f"%{username}%"))
    if parent_admin_id is not None:
        q = q.filter(Admin.parent_admin_id == parent_admin_id)
    else:
        q = q.filter(Admin.parent_admin_id == current_admin.id)

    total = q.count()
    response.headers["X-Total-Count"] = str(total)

    admins_list = q.order_by(Admin.id).offset(offset).limit(limit).all()

    result = []
    for adm in admins_list:
        user_count = (
            db.query(func.count(User.id))
            .filter(User.admin_id == adm.id, User.revoked.is_(False))
            .scalar()
            or 0
        )
        limitless_user_count = (
            db.query(func.count(User.id))
            .filter(User.admin_id == adm.id, User.revoked.is_(False), User.data_limit.is_(None))
            .scalar()
            or 0
        )
        result.append(AdminWithStatsResponse(
            id=adm.id,
            username=adm.username,
            is_sudo=adm.is_sudo,
            disabled=adm.disabled,
            created_at=adm.created_at,
            data_limit=adm.data_limit,
            data_used=adm.data_used,
            parent_admin_id=adm.parent_admin_id,
            user_count=user_count,
            limitless_user_count=limitless_user_count,
        ))
    return result


@router.get("/{admin_id}", response_model=AdminResponse)
def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Get a specific admin by ID.  Only sudo admins can view admins."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
    return admin


@router.put("/{admin_id}", response_model=AdminResponse)
def update_admin(
    admin_id: int,
    body: AdminUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Update an admin — change data_limit, disable, or reset password.

    When changing data_limit, validate the new limit is not less than
    the current sum of allocated traffic to child admins + users.
    """
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    if body.data_limit is not None and admin.data_limit is not None:
        # Calculate current allocation
        child_limit = (
            db.query(Admin.data_limit)
            .filter(Admin.parent_admin_id == admin.id, Admin.data_limit.isnot(None))
            .all()
        )
        user_limit = (
            db.query(User.data_limit)
            .filter(User.admin_id == admin.id, User.data_limit.isnot(None))
            .all()
        )
        total_allocated = sum(r[0] for r in child_limit) + sum(r[0] for r in user_limit)
        if body.data_limit < total_allocated:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reduce limit below current allocation of {total_allocated} bytes",
            )
        admin.data_limit = body.data_limit

    if body.disabled is not None:
        admin.disabled = body.disabled
        write_admin_log(
            db,
            admin_id=current_admin.id,
            action=AdminAction.UPDATE_ADMIN,
            target_type=TargetType.ADMIN,
            target_id=admin.id,
            detail=f"Set disabled={body.disabled} for admin '{admin.username}'",
        )

    if body.password is not None:
        import datetime as dt

        admin.hashed_password = hash_password(body.password)
        admin.password_reset_at = dt.datetime.now(dt.UTC)
        write_admin_log(
            db,
            admin_id=current_admin.id,
            action=AdminAction.UPDATE_ADMIN,
            target_type=TargetType.ADMIN,
            target_id=admin.id,
            detail=f"Reset password for admin '{admin.username}'",
        )

    if body.data_limit is not None:
        write_admin_log(
            db,
            admin_id=current_admin.id,
            action=AdminAction.UPDATE_ADMIN,
            target_type=TargetType.ADMIN,
            target_id=admin.id,
            detail=f"Changed data_limit to {body.data_limit} for admin '{admin.username}'",
        )

    db.commit()
    db.refresh(admin)

    # Emit appropriate notification based on what changed.
    if body.disabled is not None:
        action = "admin_disabled" if body.disabled else "admin_enabled"
    elif body.password is not None:
        action = "admin_updated"
    else:
        action = "admin_updated"

    from app.bot.formatter import _fmt_bytes

    emit(
        category=EventCategory.ADMIN_ACTION,
        action=action,
        username=admin.username,
        admin_username=current_admin.username,
        belongs_to=current_admin.username,
        data_limit=admin.data_limit,
        data_limit_str=_fmt_bytes(admin.data_limit) if admin.data_limit else None,
    )

    return admin


@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Delete an admin.  Blocked if the admin has users or child admins."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    if admin.is_sudo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete a sudo admin",
        )

    user_count = db.query(User).filter(User.admin_id == admin.id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete admin '{admin.username}': "
                f"{user_count} user(s) still assigned. "
                "Remove or reassign them first."
            ),
        )

    child_count = db.query(Admin).filter(Admin.parent_admin_id == admin.id).count()
    if child_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete admin '{admin.username}': "
                f"{child_count} sub-admin(s) still report to this admin. "
                "Delete or reassign them first."
            ),
        )

    write_admin_log(
        db,
        admin_id=current_admin.id,
        action=AdminAction.DELETE_ADMIN,
        target_type=TargetType.ADMIN,
        target_id=admin.id,
        detail=f"Deleted admin '{admin.username}'",
    )
    db.delete(admin)
    db.commit()

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="admin_deleted",
        username=admin.username,
        admin_username=current_admin.username,
        belongs_to=current_admin.username,
    )


@router.get("/{admin_id}/usage", response_model=AdminUsageResponse)
def get_admin_usage(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Get quota usage breakdown for an admin."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    child_admins_bytes = (
        db.query(func.sum(Admin.data_used))
        .filter(Admin.parent_admin_id == admin.id)
        .scalar()
        or 0
    )
    direct_users_bytes = (
        db.query(func.sum(User.data_used))
        .filter(User.admin_id == admin.id)
        .scalar()
        or 0
    )

    remaining = remaining_allocatable(admin, db)

    return AdminUsageResponse(
        admin_id=admin.id,
        username=admin.username,
        data_limit=admin.data_limit,
        data_used=admin.data_used,
        remaining=remaining,
        child_admins_bytes=child_admins_bytes,
        direct_users_bytes=direct_users_bytes,
    )

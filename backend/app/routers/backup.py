"""Backup & restore API — sudo-only full-panel backup management.

Endpoints:
    GET    /api/backup/config  → scheduled-backup settings
    PUT    /api/backup/config  → update settings
    POST   /api/backup/create  → create a backup now (optional Telegram delivery)
    GET    /api/backup/list   → archived backups
    GET    /api/backup/download?name=… → download an archive/part
    DELETE /api/backup/{name} → delete an archive (+ its split parts)
    POST   /api/backup/restore → upload a backup file and restore the panel

Restore is destructive: the current panel state is *replaced* by the backup.
"""

from __future__ import annotations

import gzip
import pathlib
import tarfile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.bot.backup import notify_backup
from app.config import BACKUP_DIR
from app.db import get_db
from app.models.admin import Admin
from app.models.backup_config import BackupConfig, get_backup_config
from app.services import backup as backup_service
from app.services.auth import get_current_sudo_admin

router = APIRouter(prefix="/api/backup", tags=["backup"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BackupConfigResponse(BaseModel):
    enabled: bool
    schedule_hour: int
    schedule_minute: int
    send_to_telegram: bool
    keep_count: int
    last_run_at: str | None = None
    last_backup_file: str


class BackupConfigUpdate(BaseModel):
    enabled: bool | None = Field(default=None)
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    schedule_minute: int | None = Field(default=None, ge=0, le=59)
    send_to_telegram: bool | None = Field(default=None)
    keep_count: int | None = Field(default=None, ge=0, le=365)


class BackupCreateRequest(BaseModel):
    send_to_telegram: bool = Field(default=False)


class BackupCreateResponse(BaseModel):
    filename: str
    size_bytes: int
    created_at: str
    server_ip: str
    includes_pki: bool
    includes_server_conf: bool


class BackupListEntry(BaseModel):
    name: str
    size_bytes: int
    created_at: str


class BackupRestoreResponse(BaseModel):
    counts: dict
    pki_restored: bool
    server_conf_restored: bool
    openvpn_restarted: bool


def _config_to_response(cfg: BackupConfig) -> BackupConfigResponse:
    return BackupConfigResponse(
        enabled=cfg.enabled,
        schedule_hour=cfg.schedule_hour,
        schedule_minute=cfg.schedule_minute,
        send_to_telegram=cfg.send_to_telegram,
        keep_count=cfg.keep_count,
        last_run_at=cfg.last_run_at.isoformat() if cfg.last_run_at else None,
        last_backup_file=cfg.last_backup_file,
    )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@router.get("/config", response_model=BackupConfigResponse)
def get_backup_settings(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    return _config_to_response(get_backup_config(db))


@router.put("/config", response_model=BackupConfigResponse)
def update_backup_settings(
    body: BackupConfigUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    cfg = get_backup_config(db)
    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(cfg, field_name, value)
    db.commit()
    db.refresh(cfg)
    return _config_to_response(cfg)


# ---------------------------------------------------------------------------
# Create / list / download / delete
# ---------------------------------------------------------------------------

@router.post("/create", response_model=BackupCreateResponse)
def create_backup_now(
    body: BackupCreateRequest | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Create a full-panel backup immediately."""
    send_telegram = bool(body and body.send_to_telegram)
    try:
        meta = backup_service.create_backup(db)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write backup archive: {exc}",
        ) from exc

    if send_telegram:
        notify_backup(meta)

    return BackupCreateResponse(**meta)


@router.get("/list", response_model=list[BackupListEntry])
def list_backup_archives(
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    return backup_service.list_backups()


@router.get("/download")
def download_backup(
    name: str = Query(...),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Download an archive (or a split part).  Path-traversal-safe."""
    if not backup_service.is_valid_filename(name):
        raise HTTPException(status_code=400, detail="Invalid backup filename.")
    path = pathlib.Path(BACKUP_DIR) / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Backup not found.")
    return FileResponse(
        path,
        media_type="application/gzip",
        filename=name,
    )


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backup_archive(
    name: str,
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Delete an archive together with any split parts."""
    if not backup_service.delete_backup(name):
        raise HTTPException(status_code=404, detail="Backup not found.")


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

@router.post("/restore", response_model=BackupRestoreResponse)
def restore_panel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Restore the panel from an uploaded backup archive.  Destructive."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No backup file uploaded.")

    dest = pathlib.Path(BACKUP_DIR) / "__restore_upload.tmp"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open("wb") as out:
            for chunk in iter(lambda: file.file.read(1024 * 1024), b""):
                out.write(chunk)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded backup: {exc}",
        ) from exc
    finally:
        file.file.close()

    try:
        summary = backup_service.restore_backup(db, str(dest))
    except (ValueError, tarfile.TarError, gzip.BadGzipFile, EOFError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Restore failed: {exc}") from exc

    return BackupRestoreResponse(**summary)

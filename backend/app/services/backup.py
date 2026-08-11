"""Full-panel backup & restore service.

Backup format: a single ``.tar.gz`` archive containing:

* ``manifest.json`` — format version, app version, creation time, per-table counts
* ``data.json``      — serialized rows for every table (admins, users, server
  config, billing ledger, audit logs, usage logs, JWT secret, backup config),
  so restoring brings the panel back to exactly the backed-up state
* ``pki/``           — the easy-rsa PKI (client certs/keys).  A restored panel
  is useless without the actual certificates, so they travel with the DB.
* ``server.conf``    — the generated OpenVPN server configuration

Database rows are serialized generically by column type (datetime → ISO,
enums → value, JSON → passthrough), which keeps every current and future
table in a backup with no per-table code.  Restore rebuilds rows with their
original primary keys inside a single transaction (safe rollback on error)
and best-effort re-imports the PKI + server.conf before restarting OpenVPN.
"""

from __future__ import annotations

import datetime as dt
import enum
import json
import logging
import pathlib
import re
import shutil
import tarfile
import tempfile

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.config import APP_VERSION, BACKUP_DIR, EASYRSA_DIR
from app.models import (
    Admin,
    AdminLog,
    BackupConfig,
    BillingRecord,
    JWTSecret,
    ServerConfig,
    UsageLog,
    User,
)

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1

# Everything that makes up the panel state, in FK-safe load order.
# (admins are loaded in two passes: rows first, then parent_admin_id links.)
_TABLES: list[type] = [
    Admin,
    User,
    ServerConfig,
    BillingRecord,
    AdminLog,
    UsageLog,
    JWTSecret,
    BackupConfig,
]

# Delete order is the reverse of the dependency graph so FK constraints in
# strict databases (Postgres, SQLite with PRAGMA foreign_keys=ON) never fire.
_DELETE_ORDER: list[type] = [
    UsageLog,
    AdminLog,
    BillingRecord,
    User,
    Admin,
    ServerConfig,
    JWTSecret,
    BackupConfig,
]

_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def is_valid_filename(name: str) -> bool:
    """Reject anything that could escape the backup directory (path traversal)."""
    return bool(_FILENAME_RE.match(name))

# Telegram's sendDocument limit is 50 MB — split archives at a safe size.
SPLIT_CHUNK_BYTES = 45 * 1024 * 1024


# ---------------------------------------------------------------------------
# Serialization helpers (generic by column type)
# ---------------------------------------------------------------------------

def _ser(value):
    if value is None:
        return None
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _deser(coltype, value):
    if value is None:
        return None
    if isinstance(coltype, sa.DateTime):
        parsed = dt.datetime.fromisoformat(value)
        return parsed.replace(tzinfo=dt.UTC) if parsed.tzinfo is None else parsed
    if isinstance(coltype, sa.Time):
        return dt.time.fromisoformat(value)
    if isinstance(coltype, sa.Enum) and coltype.enum_class is not None:
        return coltype.enum_class(value)
    return value


def _row_to_dict(row, model: type) -> dict:
    out: dict = {}
    for col in model.__table__.columns:
        out[col.name] = _ser(getattr(row, col.name))
    return out


def _dict_to_row(model: type, data: dict):
    kwargs = {}
    for col in model.__table__.columns:
        if col.name not in data:
            continue
        kwargs[col.name] = _deser(col.type, data[col.name])
    return model(**kwargs)


# ---------------------------------------------------------------------------
# Database dump / restore
# ---------------------------------------------------------------------------

def _dump_database(db: Session) -> dict:
    data: dict[str, list] = {}
    for model in _TABLES:
        rows = db.query(model).all()
        data[model.__tablename__] = [_row_to_dict(r, model) for r in rows]
    return data


def _restore_database(db: Session, data: dict) -> dict:
    """Wipe every table and rebuild it from the backup, all in one transaction.

    Original primary keys are preserved so foreign keys and audit history
    keep pointing at the right rows.  Postgres autoincrement sequences are
    re-synced afterwards.
    """
    counts: dict[str, int] = {}

    for model in _DELETE_ORDER:
        db.query(model).delete(synchronize_session="fetch")
    db.flush()

    # Admins first (base fields), then wire up the hierarchy.
    admin_rows = data.get("admins", [])
    for row in admin_rows:
        db.add(_dict_to_row(Admin, {**row, "parent_admin_id": None}))
    db.flush()
    for row in admin_rows:
        if row.get("parent_admin_id") is not None:
            parent = db.query(Admin).filter(Admin.id == row["parent_admin_id"]).first()
            if parent is not None:
                db.query(Admin).filter(Admin.id == row["id"]).update(
                    {"parent_admin_id": row["parent_admin_id"]}
                )
                db.flush()

    for model in _TABLES:
        if model is Admin:
            counts["admins"] = len(admin_rows)
            continue
        rows = data.get(model.__tablename__, [])
        for row in rows:
            db.add(_dict_to_row(model, row))
        db.flush()
        counts[model.__tablename__] = len(rows)

    _fix_postgres_sequences(db)
    return counts


def _fix_postgres_sequences(db: Session) -> None:
    """Re-sync identity sequences after inserting rows with explicit IDs."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    for model in _TABLES:
        table = model.__table__.name
        for pk in model.__table__.primary_key.columns:
            # Identifiers come from our own model definitions — safe to inline.
            query = (
                f"SELECT setval(pg_get_serial_sequence('{table}', '{pk.name}'), "
                f"COALESCE((SELECT MAX({pk.name}) FROM {table}), 1))"
            )
            db.execute(sa.text(query))


# ---------------------------------------------------------------------------
# Archive building
# ---------------------------------------------------------------------------

def _archive_name(created_at: dt.datetime) -> str:
    return created_at.astimezone(dt.UTC).strftime("backup_%Y%m%d_%H%M%S.tar.gz")


def _server_ip(db: Session) -> str:
    cfg = db.query(ServerConfig).first()
    if cfg is not None and cfg.public_host:
        return cfg.public_host
    try:
        from app.db.seed import _detect_public_ip

        return _detect_public_ip()
    except Exception:
        pass
    return ""


def _stage_archive(db: Session, staging: pathlib.Path) -> dict:
    """Write manifest.json, data.json, pki/ and server.conf into *staging*."""
    created_at = dt.datetime.now(dt.UTC).replace(tzinfo=dt.UTC)
    data = _dump_database(db)
    manifest = {
        "format_version": FORMAT_VERSION,
        "app_version": APP_VERSION,
        "created_at": created_at.isoformat(),
        "server_ip": _server_ip(db),
        "counts": {model.__tablename__: len(data[model.__tablename__]) for model in _TABLES},
        "includes_pki": False,
        "includes_server_conf": False,
    }

    # OpenVPN PKI — best effort, non-fatal if the host paths aren't there
    # (tests, dev machines, first installs).
    pki_dir = pathlib.Path(EASYRSA_DIR) / "pki"
    if pki_dir.is_dir():
        try:
            shutil.copytree(pki_dir, staging / "pki", dirs_exist_ok=True)
            manifest["includes_pki"] = True
        except OSError as exc:
            logger.warning("Could not stage PKI into backup: %s", exc)

    server_conf = pathlib.Path("/opt/eovpanel/vpn/server.conf")
    if server_conf.is_file():
        try:
            shutil.copy2(server_conf, staging / "server.conf")
            manifest["includes_server_conf"] = True
        except OSError as exc:
            logger.warning("Could not stage server.conf into backup: %s", exc)

    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (staging / "data.json").write_text(json.dumps(data, default=str), encoding="utf-8")
    return manifest


def create_backup(db: Session, *, name: str | None = None) -> dict:
    """Create a full-panel backup archive in BACKUP_DIR.

    Returns a dict with the filename, absolute path, size and creation time.
    """
    backup_dir = pathlib.Path(BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)

    created_at = dt.datetime.now(dt.UTC).replace(tzinfo=dt.UTC)
    filename = name or _archive_name(created_at)
    if not _FILENAME_RE.match(filename):
        raise ValueError("Backup filename must be alphanumeric with dots/underscores/dashes.")

    # Rare same-second collisions (e.g. double-click on "Backup Now") would
    # silently overwrite the previous file — disambiguate with microseconds.
    if name is None:
        candidate = pathlib.Path(BACKUP_DIR) / filename
        if candidate.exists():
            filename = created_at.astimezone(dt.UTC).strftime("backup_%Y%m%d_%H%M%S_%f.tar.gz")

    with tempfile.TemporaryDirectory(prefix="eovpanel-backup-") as tmp:
        staging = pathlib.Path(tmp) / "staging"
        staging.mkdir()
        manifest = _stage_archive(db, staging)
        manifest["created_at"] = created_at.isoformat()

        archive_path = backup_dir / filename
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(staging, arcname=".")

    size = archive_path.stat().st_size
    logger.info(
        "Backup created: %s (%d bytes, pki=%s, server_conf=%s)",
        filename,
        size,
        manifest["includes_pki"],
        manifest["includes_server_conf"],
    )
    return {
        "filename": filename,
        "path": str(archive_path),
        "size_bytes": size,
        "created_at": created_at.isoformat(),
        "server_ip": manifest["server_ip"],
        "includes_pki": manifest["includes_pki"],
        "includes_server_conf": manifest["includes_server_conf"],
        "counts": manifest["counts"],
    }


# ---------------------------------------------------------------------------
# Archive listing / deletion / pruning / splitting
# ---------------------------------------------------------------------------

def list_backups() -> list[dict]:
    """Return archived backups sorted newest-first, excluding split temp files' dirs."""
    backup_dir = pathlib.Path(BACKUP_DIR)
    if not backup_dir.is_dir():
        return []
    entries = []
    for path in backup_dir.iterdir():
        if not path.is_file() or not path.name.endswith((".tar.gz", ".tar")):
            continue
        entries.append(
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "created_at": dt.datetime.fromtimestamp(path.stat().st_mtime, dt.UTC).isoformat(),
            }
        )
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries


def _parts_of(archive_path: pathlib.Path) -> list[pathlib.Path]:
    """Return all split-part files belonging to *archive_path* (if any)."""
    stem = archive_path.stem  # backup_..._220003.tar  (full archive's stem)
    parts = []
    for sibling in archive_path.parent.iterdir():
        if sibling.name.startswith(stem) and "_part_" in sibling.name and sibling.is_file():
            parts.append(sibling)
    return sorted(parts)


def delete_backup(name: str) -> bool:
    """Delete an archive and any split parts behind it.  Returns False if absent."""
    if not _FILENAME_RE.match(name):
        return False
    path = pathlib.Path(BACKUP_DIR) / name
    parts = _parts_of(path)
    removed = False
    for p in [path, *parts]:
        if p.is_file():
            try:
                p.unlink()
                removed = True
            except OSError:
                logger.warning("Backup deletion failed for %s", p)
    return removed


def prune_backups(keep_count: int) -> int:
    """Delete oldest archives beyond *keep_count* (0 = keep all).  Returns count removed."""
    if keep_count <= 0:
        return 0
    backups = sorted(
        (pathlib.Path(BACKUP_DIR) / e["name"] for e in list_backups()),
        key=lambda p: p.stat().st_mtime,
    )
    removed = 0
    for path in backups[:-keep_count]:
        if delete_backup(path.name):
            removed += 1
    return removed


def split_backup(path: pathlib.Path, chunk_bytes: int = SPLIT_CHUNK_BYTES) -> list[str]:
    """Split a large archive into ``_part_aa/_part_ab/...`` files side by side.

    Used to deliver backups over Telegram (50 MB sendDocument limit).  Returns
    the list of part filenames.
    """
    if path.stat().st_size <= chunk_bytes:
        return [path.name]
    stem = path.stem  # e.g. backup_20260808_220003.tar
    part_names: list[str] = []
    with open(path, "rb") as src:
        index = 0
        while True:
            chunk = src.read(chunk_bytes)
            if not chunk:
                break
            if index >= 26:
                raise ValueError("Backup too large to split into Telegram-sized parts.")
            tag = f"part_{chr(97 + index)}"
            part_name = f"{stem}_{tag}.tar.gz"
            part_path = path.parent / part_name
            with open(part_path, "wb") as out:
                out.write(chunk)
            part_names.append(part_name)
            index += 1
    return part_names


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def restore_backup(db: Session, archive_path: str) -> dict:
    """Restore the panel from a backup archive.

    Steps:
      1. Extract to a temp dir and validate manifest + data.json.
      2. Swap the whole DB in one transaction (rollback-safe).
      3. Best-effort re-import PKI + server.conf and restart OpenVPN.

    Returns a summary dict of what was restored.
    """
    archive = pathlib.Path(archive_path)
    if not archive.is_file():
        raise FileNotFoundError(f"Backup archive not found: {archive_path}")

    with tempfile.TemporaryDirectory(prefix="eovpanel-restore-") as tmp:
        extract_dir = pathlib.Path(tmp) / "extract"
        extract_dir.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                # Guard against path traversal inside the archive.
                target = (extract_dir / member.name).resolve()
                if not str(target).startswith(str(extract_dir.resolve())):
                    raise ValueError(f"Archive contains an unsafe path: {member.name}")
            tar.extractall(extract_dir, filter="data")

        manifest_path = extract_dir / "manifest.json"
        data_path = extract_dir / "data.json"
        if not manifest_path.is_file() or not data_path.is_file():
            raise ValueError("Invalid backup: missing manifest.json or data.json.")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format_version") != FORMAT_VERSION:
            raise ValueError(
                f"Unsupported backup format {manifest.get('format_version')} "
                f"(this panel expects {FORMAT_VERSION})."
            )
        data = json.loads(data_path.read_text(encoding="utf-8"))

        # --- Swap the database transactionally ---
        try:
            counts = _restore_database(db, data)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Database restore failed — rolled back to previous state")
            raise

        # --- Re-import PKI + server.conf (best effort) ---
        pki_restored = _restore_pki(extract_dir)
        conf_restored = _restore_server_conf(extract_dir)
        openvpn_restarted = bool(pki_restored or conf_restored)
        if openvpn_restarted:
            _restart_openvpn(db)

        logger.info(
            "Restore complete: %d admins, %d users; pki=%s server_conf=%s",
            counts.get("admins", 0),
            counts.get("users", 0),
            pki_restored,
            conf_restored,
        )
        return {
            "counts": counts,
            "pki_restored": pki_restored,
            "server_conf_restored": conf_restored,
            "openvpn_restarted": openvpn_restarted,
        }


def _restore_pki(extract_dir: pathlib.Path) -> bool:
    """Replace the live easy-rsa PKI with the backed-up one.  Returns success."""
    src = extract_dir / "pki"
    if not src.is_dir():
        return False
    target = pathlib.Path(EASYRSA_DIR) / "pki"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = target.parent / "pki.bak-restore"
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        if target.exists():
            target.rename(backup)
        shutil.copytree(src, target)
        shutil.rmtree(backup, ignore_errors=True)
        return True
    except OSError as exc:
        logger.error("PKI restore failed: %s", exc)
        return False


def _restore_server_conf(extract_dir: pathlib.Path) -> bool:
    """Replace server.conf if the archive contains one.  Returns success."""
    src = extract_dir / "server.conf"
    if not src.is_file():
        return False
    try:
        target = pathlib.Path("/opt/eovpanel/vpn/server.conf")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        return True
    except OSError as exc:
        logger.error("server.conf restore failed: %s", exc)
        return False


def _restart_openvpn(db: Session) -> None:
    """Best-effort OpenVPN restart using the restored server config."""
    try:
        from app.services.vpn_bridge import apply_server_config

        cfg = db.query(ServerConfig).first()
        if cfg is None:
            return
        _tls = cfg.tls_mode.value if hasattr(cfg.tls_mode, "value") else str(cfg.tls_mode)
        tls_crypt = _tls == "tls-crypt"
        tls_auth = _tls == "tls-auth"
        apply_server_config(
            protocol=cfg.protocol.value,
            port=cfg.port,
            interface=cfg.interface,
            cipher=cfg.cipher.value,
            auth=cfg.auth_digest.value,
            dns_servers=cfg.dns_servers,
            mtu=cfg.mtu,
            keepalive_interval=cfg.keepalive_interval,
            keepalive_timeout=cfg.keepalive_timeout,
            client_to_client=cfg.client_to_client,
            redirect_gateway=cfg.redirect_gateway,
            public_ip=cfg.public_host,
            tls_crypt=tls_crypt,
            tls_auth=tls_auth,
        )
    except Exception as exc:
        logger.warning("OpenVPN restart after restore failed (non-fatal): %s", exc)

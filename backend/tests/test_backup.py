"""Tests for the backup service and /api/backup router.

Backup archives are stored in a per-test temp dir (the real BACKUP_DIR under
/opt is a host path that doesn't exist in CI).  The easy-rsa PKI is pointed
at a non-existent temp path so archives are deterministic and small.
"""

from __future__ import annotations

import gzip
import io
import tarfile

import pytest

from app.db.seed import seed_default_server_config, seed_sudo_admin
from app.models.admin import Admin
from app.models.server_config import Protocol, ServerConfig
from app.models.user import User

pytestmark = pytest.mark.usefixtures("db_session")

BACKUP_DIR_KEY = "app.services.backup.BACKUP_DIR"
ROUTER_BACKUP_DIR_KEY = "app.routers.backup.BACKUP_DIR"
EASYRSA_KEY = "app.services.backup.EASYRSA_DIR"


@pytest.fixture()
def panel_backup_dir(tmp_path, monkeypatch, db_session):
    """Point backup storage into a temp dir and seed a small panel."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    monkeypatch.setattr(BACKUP_DIR_KEY, str(backup_dir))
    monkeypatch.setattr(ROUTER_BACKUP_DIR_KEY, str(backup_dir))
    monkeypatch.setattr(EASYRSA_KEY, str(tmp_path / "easy-rsa" / "nonexistent"))
    return backup_dir


@pytest.fixture()
def seeded_panel(db_session):
    """A realistic panel state to back up."""
    seed_sudo_admin(db_session)
    seed_default_server_config(db_session)
    db_session.commit()

    sudo = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
    child = Admin(
        username="reseller",
        hashed_password="x-hash",
        is_sudo=False,
        disabled=False,
        data_limit=2 * 1024**3,
        data_used=0,
        parent_admin_id=sudo.id,
    )
    db_session.add(child)
    db_session.flush()

    db_session.add(
        User(
            username="alice",
            admin_id=child.id,
            data_limit=10 * 1024**3,
            data_used=2 * 1024**3,
            expire_at=None,
            note="VIP",
            revoked=False,
        )
    )
    db_session.add(
        User(
            username="bob",
            admin_id=child.id,
            data_limit=None,
            data_used=0,
            expire_at=None,
            note="Unlimited",
            revoked=True,  # soft-deleted row must also round-trip
        )
    )
    db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# Service: create + dump fidelity
# ---------------------------------------------------------------------------

class TestCreateBackup:
    def test_archive_created_and_valid(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        meta = backup_service.create_backup(seeded_panel)
        assert meta["filename"].endswith(".tar.gz")
        assert (panel_backup_dir / meta["filename"]).is_file()
        assert meta["size_bytes"] > 0

        with tarfile.open(str(panel_backup_dir / meta["filename"]), "r:gz") as tar:
            names = tar.getnames()
            assert any(n.endswith("manifest.json") for n in names)
            assert any(n.endswith("data.json") for n in names)

    def test_rejects_unsafe_filename(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        with pytest.raises(ValueError):
            backup_service.create_backup(seeded_panel, name="../escape.tar.gz")

    def test_dump_contains_every_row(self, panel_backup_dir, seeded_panel):
        data = seeded_panel.query(User).count()
        assert data == 2  # both rows (active + revoked) are captured
        admins = seeded_panel.query(Admin).count()
        assert admins == 2

    def test_listing_and_delete(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        meta = backup_service.create_backup(seeded_panel)
        entries = backup_service.list_backups()
        assert [e["name"] for e in entries] == [meta["filename"]]

        assert backup_service.delete_backup(meta["filename"]) is True
        assert backup_service.list_backups() == []
        assert backup_service.delete_backup(meta["filename"]) is False

    def test_prune_keeps_newest(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        for _ in range(4):
            backup_service.create_backup(seeded_panel)
        assert backup_service.prune_backups(2) == 2
        assert len(backup_service.list_backups()) == 2

    def test_split_small_archive_unchanged(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        meta = backup_service.create_backup(seeded_panel)
        parts = backup_service.split_backup(
            panel_backup_dir / meta["filename"], chunk_bytes=10 * 1024 * 1024
        )
        assert parts == [meta["filename"]]

    def test_split_large_archive(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        meta = backup_service.create_backup(seeded_panel)
        parts = backup_service.split_backup(
            panel_backup_dir / meta["filename"], chunk_bytes=100
        )
        assert len(parts) > 1
        for p in parts:
            assert p.startswith("part_") is False
            assert "_part_" in p


# ---------------------------------------------------------------------------
# Service: restore round-trip
# ---------------------------------------------------------------------------

class TestRestoreBackup:
    def test_restore_rebuilds_exact_state(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        meta = backup_service.create_backup(seeded_panel)

        # Mess up the live DB to prove restore replaces everything.
        seeded_panel.query(User).delete(synchronize_session=False)
        seeded_panel.query(Admin).delete(synchronize_session=False)
        seeded_panel.commit()
        assert seeded_panel.query(User).count() == 0

        summary = backup_service.restore_backup(
            seeded_panel, str(panel_backup_dir / meta["filename"])
        )
        assert summary["counts"]["users"] == 2
        assert summary["counts"]["admins"] == 2
        assert summary["pki_restored"] is False
        assert summary["server_conf_restored"] is False

        # Full fidelity check.
        admins = seeded_panel.query(Admin).order_by(Admin.id).all()
        usernames = {a.username for a in admins}
        assert usernames == {"admin", "reseller"}
        reseller = seeded_panel.query(Admin).filter(Admin.username == "reseller").first()
        assert reseller.data_limit == 2 * 1024**3
        assert reseller.parent_admin_id is not None

        users = seeded_panel.query(User).order_by(User.username).all()
        assert [u.username for u in users] == ["alice", "bob"]
        alice = seeded_panel.query(User).filter(User.username == "alice").first()
        assert alice.data_limit == 10 * 1024**3
        assert alice.data_used == 2 * 1024**3
        assert alice.note == "VIP"
        bob = seeded_panel.query(User).filter(User.username == "bob").first()
        assert bob.revoked is True
        assert bob.subscription_token != ""

        cfg = seeded_panel.query(ServerConfig).first()
        assert cfg.protocol == Protocol.UDP

    def test_restore_preserves_server_config_enums(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        cfg = seeded_panel.query(ServerConfig).first()
        cfg.port = 1987
        seeded_panel.commit()

        meta = backup_service.create_backup(seeded_panel)
        seeded_panel.query(ServerConfig).delete(synchronize_session=False)
        seeded_panel.commit()

        backup_service.restore_backup(seeded_panel, str(panel_backup_dir / meta["filename"]))
        restored = seeded_panel.query(ServerConfig).first()
        assert restored.port == 1987

    def test_invalid_archive_rejected(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        bogus = panel_backup_dir / "bogus.tar.gz"
        bogus.write_bytes(gzip.compress(b"not a real backup"))
        with pytest.raises((tarfile.TarError, ValueError, OSError)):
            backup_service.restore_backup(seeded_panel, str(bogus))

    def test_missing_archive_raises(self, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        with pytest.raises(FileNotFoundError):
            backup_service.restore_backup(seeded_panel, str(panel_backup_dir / "nope.tar.gz"))


# ---------------------------------------------------------------------------
# Scheduled job
# ---------------------------------------------------------------------------

class TestBackupJob:
    @pytest.fixture()
    def job_env(self, panel_backup_dir, db_session, monkeypatch):
        """Patch the job's SessionLocal to the test session."""
        monkeypatch.setattr("app.jobs.backup.SessionLocal", lambda: db_session)
        from app.models.backup_config import get_backup_config

        cfg = get_backup_config(db_session)
        cfg.last_run_at = None
        cfg.last_backup_file = ""
        db_session.commit()
        return db_session

    def _set_schedule(self, db_session, enabled=True):
        import datetime as dt

        from app.models.backup_config import get_backup_config

        now = dt.datetime.now(dt.UTC)
        cfg = get_backup_config(db_session)
        cfg.enabled = enabled
        cfg.schedule_hour = now.hour
        cfg.schedule_minute = now.minute
        cfg.send_to_telegram = False
        cfg.last_run_at = None
        db_session.commit()
        return cfg

    def test_disabled_does_nothing(self, job_env):
        from app.jobs.backup import backup_job
        from app.services import backup as backup_service

        self._set_schedule(job_env, enabled=False)
        backup_job()
        assert backup_service.list_backups() == []

    def test_wrong_time_does_nothing(self, job_env):
        import datetime as dt

        from app.jobs.backup import backup_job

        cfg = self._set_schedule(job_env)
        cfg.schedule_hour = (dt.datetime.now(dt.UTC).hour + 1) % 24
        job_env.commit()

        backup_job()
        from app.services import backup as backup_service

        assert backup_service.list_backups() == []

    def test_runs_at_scheduled_time(self, job_env):
        import datetime as dt

        from app.jobs.backup import backup_job
        from app.models.backup_config import get_backup_config
        from app.services import backup as backup_service

        cfg = self._set_schedule(job_env)
        cfg.send_to_telegram = True  # bot not configured → silently skipped
        job_env.commit()

        backup_job()

        entries = backup_service.list_backups()
        assert len(entries) == 1
        refreshed = get_backup_config(job_env)
        assert refreshed.last_backup_file == entries[0]["name"]
        assert refreshed.last_run_at is not None
        assert refreshed.last_run_at.date() == dt.datetime.now(dt.UTC).date()

    def test_runs_once_per_day(self, job_env):
        from app.jobs.backup import backup_job
        from app.services import backup as backup_service

        self._set_schedule(job_env)
        backup_job()
        backup_job()  # same day → second call is a no-op
        assert len(backup_service.list_backups()) == 1


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class TestBackupApi:
    def test_config_defaults(self, sudo_client):
        resp = sudo_client.get("/api/backup/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is False
        assert body["schedule_hour"] == 3
        assert body["keep_count"] == 7

    def test_update_config(self, sudo_client):
        resp = sudo_client.put(
            "/api/backup/config",
            json={"enabled": True, "schedule_hour": 6, "send_to_telegram": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert body["schedule_hour"] == 6
        assert body["send_to_telegram"] is True

    def test_create_list_download_delete(self, sudo_client, panel_backup_dir, seeded_panel):
        resp = sudo_client.post("/api/backup/create", json={"send_to_telegram": False})
        assert resp.status_code == 200, resp.text
        meta = resp.json()
        assert meta["filename"].endswith(".tar.gz")

        entries = sudo_client.get("/api/backup/list").json()
        assert [e["name"] for e in entries if e["name"] == meta["filename"]]

        dl = sudo_client.get("/api/backup/download", params={"name": meta["filename"]})
        assert dl.status_code == 200
        assert dl.headers["content-type"] == "application/gzip"
        assert dl.content == (panel_backup_dir / meta["filename"]).read_bytes()

        bad = sudo_client.get("/api/backup/download", params={"name": "../../etc/passwd"})
        assert bad.status_code == 400

        rm = sudo_client.delete(f"/api/backup/{meta['filename']}")
        assert rm.status_code == 204
        assert sudo_client.get("/api/backup/list").json() == []

    def test_restore_via_api(self, sudo_client, panel_backup_dir, seeded_panel):
        from app.services import backup as backup_service

        meta = backup_service.create_backup(seeded_panel)
        archive = (panel_backup_dir / meta["filename"]).read_bytes()

        seeded_panel.query(User).delete(synchronize_session=False)
        seeded_panel.commit()
        assert seeded_panel.query(User).count() == 0

        resp = sudo_client.post(
            "/api/backup/restore",
            files={"file": (meta["filename"], io.BytesIO(archive), "application/gzip")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["counts"]["users"] == 2
        assert seeded_panel.query(User).count() == 2

    def test_restore_rejects_junk(self, sudo_client, panel_backup_dir):
        resp = sudo_client.post(
            "/api/backup/restore",
            files={"file": ("junk.tar.gz", io.BytesIO(b"not a tar"), "application/gzip")},
        )
        assert resp.status_code == 400  # safe failed restore, state untouched

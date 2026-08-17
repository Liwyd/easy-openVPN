"""Utility helpers — OS detection, file I/O, subprocess, IP lookup."""

from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Path constants (mirrors the repo layout)
# ---------------------------------------------------------------------------
REPO_ROOT = Path("/opt/eovpanel")
VPN_CORE = REPO_ROOT / "vpn-core"
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
DOCKER_DIR = REPO_ROOT / "docker"
COMPOSE_FILE = DOCKER_DIR / "docker-compose.yml"
ENV_EXAMPLE = BACKEND_DIR / ".env.example"
ENV_FILE = BACKEND_DIR / ".env"
REPO_ENV = REPO_ROOT / ".env"
DOCKER_ENV = DOCKER_DIR / ".env"
NGINX_CONF = FRONTEND_DIR / "nginx.conf"
OPENVPN_SERVER_DIR = Path("/opt/eovpanel/vpn")
ESSL_DIR = Path("/opt/essl")
ESSL_CERT_DIR = Path("/etc/ssl/eovpanel")


# ---------------------------------------------------------------------------
# OS / root detection
# ---------------------------------------------------------------------------
@dataclass
class OsInfo:
    distro: str
    version: str
    is_root: bool
    is_debian_like: bool


def detect_os() -> OsInfo:
    is_root = os.geteuid() == 0
    distro = "unsupported"
    version = ""
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    distro = line.split("=", 1)[1].strip().strip('"').lower()
                elif line.startswith("VERSION_ID="):
                    version = line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return OsInfo(distro=distro, version=version, is_root=is_root,
                  is_debian_like=distro in ("ubuntu", "debian"))


# ---------------------------------------------------------------------------
# Network detection
# ---------------------------------------------------------------------------
def detect_public_ip() -> str:
    for url in ("http://ip1.dynupdate.no-ip.com/", "http://ifconfig.me", "http://icanhazip.com"):
        try:
            r = subprocess.run(["curl", "-m", "5", "-4Ls", url], capture_output=True, text=True, timeout=10)
            ip = r.stdout.strip()
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
                return ip
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    try:
        r = subprocess.run(["ip", "-4", "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=5)
        m = re.search(r"src\s+([\d.]+)", r.stdout)
        if m:
            return m.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def detect_default_interface() -> str:
    try:
        r = subprocess.run(["ip", "-4", "route", "show", "default"], capture_output=True, text=True, timeout=5)
        parts = r.stdout.strip().split()
        if "dev" in parts:
            idx = parts.index("dev")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "eth0"


# ---------------------------------------------------------------------------
# OpenVPN / Docker detection
# ---------------------------------------------------------------------------
def openvpn_installed() -> bool:
    return shutil.which("openvpn") is not None or OPENVPN_SERVER_DIR.exists()


def docker_running() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def containers_running() -> list[str]:
    try:
        r = subprocess.run(
            ["docker", "ps", "--filter", "name=eovpanel", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        return [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


# ---------------------------------------------------------------------------
# ESSL (TLS) helpers
# ---------------------------------------------------------------------------
ESSL_SCRIPT_URL = "https://raw.githubusercontent.com/erfjab/ESSL/main/essl.sh"
ESSL_INSTALL_PATH = ESSL_DIR / "essl.sh"


def _ensure_certbot() -> bool:
    """Install certbot and socat if not already present."""
    try:
        subprocess.run(
            ["apt-get", "update", "-qq"],
            capture_output=True, text=True, timeout=60,
        )
        subprocess.run(
            ["apt-get", "install", "-y", "--no-install-recommends", "certbot", "socat"],
            capture_output=True, text=True, timeout=120,
        )
        return True
    except Exception:
        return False


def _ensure_acme_sh() -> bool:
    """Install acme.sh if not already present."""
    acme_bin = Path.home() / ".acme.sh" / "acme.sh"
    if acme_bin.exists():
        return True
    try:
        r = subprocess.run(
            ["curl", "-fsSL", "https://get.acme.sh", "-o", "/tmp/acme-install.sh"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return False
        subprocess.run(
            ["bash", "/tmp/acme-install.sh"],
            capture_output=True, text=True, timeout=60,
        )
        # Set default CA to Let's Encrypt
        subprocess.run(
            [str(acme_bin), "--set-default-ca", "--server", "letsencrypt"],
            capture_output=True, text=True, timeout=30,
        )
        return acme_bin.exists()
    except Exception:
        return False


def _issue_cert_certbot(domain: str, email: str, dest_dir: Path) -> tuple[bool, str]:
    """Issue a certificate using certbot standalone mode."""
    output_parts: list[str] = []
    try:
        # Stop anything on port 80 first (certbot standalone needs it)
        subprocess.run(
            ["fuser", "-k", "80/tcp"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass

    cmd = [
        "certbot", "certonly", "--standalone",
        "--non-interactive", "--agree-tos",
        "--keep-until-expiring",
        "-d", domain,
        "--email", email,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output_parts.append(r.stdout)
        output_parts.append(r.stderr)
        if r.returncode == 0:
            # Copy certs to dest_dir
            live_dir = Path(f"/etc/letsencrypt/live/{domain}")
            if (live_dir / "fullchain.pem").exists() and (live_dir / "privkey.pem").exists():
                import shutil
                shutil.copy2(live_dir / "fullchain.pem", dest_dir / "fullchain.pem")
                shutil.copy2(live_dir / "privkey.pem", dest_dir / "privkey.pem")
                return True, "\n".join(output_parts)
            return False, "\n".join(output_parts) + "\nCert files not found in letsencrypt live dir."
        return False, "\n".join(output_parts)
    except subprocess.TimeoutExpired:
        return False, "certbot timed out after 180s"
    except Exception as exc:
        return False, str(exc)


def _issue_cert_acme(domain: str, email: str, dest_dir: Path) -> tuple[bool, str]:
    """Issue a certificate using acme.sh standalone mode."""
    acme_bin = Path.home() / ".acme.sh" / "acme.sh"
    output_parts: list[str] = []
    try:
        subprocess.run(
            ["fuser", "-k", "80/tcp"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass

    cmd = [
        str(acme_bin), "--issue", "--force", "--standalone",
        "-d", domain,
        "--accountemail", email,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output_parts.append(r.stdout)
        output_parts.append(r.stderr)
        if r.returncode == 0:
            # acme.sh stores certs in ~/.acme.sh/<domain>_ecc/
            acme_cert_dir = Path.home() / ".acme.sh" / f"{domain}_ecc"
            fullchain = acme_cert_dir / "fullchain.cer"
            key = acme_cert_dir / f"{domain}.key"
            if fullchain.exists() and key.exists():
                import shutil
                shutil.copy2(fullchain, dest_dir / "fullchain.pem")
                shutil.copy2(key, dest_dir / "privkey.pem")
                return True, "\n".join(output_parts)
            return False, "\n".join(output_parts) + "\nCert files not found in acme.sh dir."
        return False, "\n".join(output_parts)
    except subprocess.TimeoutExpired:
        return False, "acme.sh timed out after 180s"
    except Exception as exc:
        return False, str(exc)


def run_essl(domain: str, email: str, dest_dir: Path) -> tuple[bool, str]:
    """Issue a TLS certificate for the given domain.

    Tries acme.sh first (faster, no interactive prompts), then falls back to
    certbot standalone.  Certificates are copied to *dest_dir* as
    fullchain.pem / privkey.pem.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    output_parts: list[str] = []

    # Try acme.sh first
    acme_ok = _ensure_acme_sh()
    if acme_ok:
        ok, out = _issue_cert_acme(domain, email, dest_dir)
        output_parts.append(f"[acme.sh] {out}")
        if ok:
            return True, "\n".join(output_parts)

    # Fall back to certbot
    certbot_ok = _ensure_certbot()
    if certbot_ok:
        ok, out = _issue_cert_certbot(domain, email, dest_dir)
        output_parts.append(f"[certbot] {out}")
        if ok:
            return True, "\n".join(output_parts)

    return False, "\n".join(output_parts) + "\nFailed to obtain certificate via acme.sh and certbot."


# ---------------------------------------------------------------------------
# .env file helpers
# ---------------------------------------------------------------------------
def read_env(path: Path | None = None) -> dict[str, str]:
    path = path or ENV_FILE
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def write_env(data: dict[str, str], path: Path | None = None) -> None:
    path = path or ENV_FILE
    lines = [f"{k}={v}" for k, v in data.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_env(updates: dict[str, str], path: Path | None = None) -> None:
    path = path or ENV_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    keys_written: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                keys_written.add(key)
                continue
        new_lines.append(line)
    for key, val in updates.items():
        if key not in keys_written:
            new_lines.append(f"{key}={val}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Subprocess helpers (synchronous, streaming)
# ---------------------------------------------------------------------------
def run_cmd(
    cmd: list[str],
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
    stream: bool = False,
) -> tuple[int, str]:
    """Run a command. If stream=True, print each line as it arrives."""
    merged = dict(os.environ)
    if env:
        merged.update(env)

    if stream:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=cwd, env=merged, text=True, bufsize=1,
        )
        output_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n\r")
            output_lines.append(line)
            print(f"    {line}")
        proc.wait(timeout=timeout)
        return proc.returncode or 0, "\n".join(output_lines)
    else:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=merged, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)


def run_cmd_bg(cmd: list[str], cwd: str | Path | None = None, env: dict[str, str] | None = None) -> subprocess.Popen:
    """Run a command in the background, return the Popen object."""
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=merged, text=True)


# ---------------------------------------------------------------------------
# Seed / bootstrap helpers
# ---------------------------------------------------------------------------
def generate_jwt_secret() -> str:
    return secrets.token_hex(32)


def seed_backend_admin(username: str, password: str) -> None:
    env = read_env(REPO_ENV)
    env["SUDO_USERNAME"] = username
    env["SUDO_PASSWORD"] = password
    env["JWT_SECRET_KEY"] = env.get("JWT_SECRET_KEY") or generate_jwt_secret()
    write_env(env, REPO_ENV)


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------
def docker_compose_pull(stream_output: bool = True) -> tuple[int, str]:
    """Pull prebuilt images from Docker Hub."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "pull"]
    return run_cmd(cmd, cwd=str(DOCKER_DIR), stream=stream_output)


def docker_compose_up(stream_output: bool = True) -> tuple[int, str]:
    """Start containers using pre-pulled images (no local build)."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"]
    return run_cmd(cmd, cwd=str(DOCKER_DIR), stream=stream_output)


def docker_compose_down(remove_volumes: bool = False, stream_output: bool = True) -> tuple[int, str]:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "down"]
    if remove_volumes:
        cmd.append("-v")
    return run_cmd(cmd, cwd=str(DOCKER_DIR), stream=stream_output)


def docker_compose_restart(stream_output: bool = True) -> tuple[int, str]:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "restart"]
    return run_cmd(cmd, cwd=str(DOCKER_DIR), stream=stream_output)

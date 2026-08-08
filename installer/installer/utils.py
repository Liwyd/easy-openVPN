"""Utility helpers — OS detection, file I/O, subprocess streaming, IP lookup."""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable


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
NGINX_CONF = FRONTEND_DIR / "nginx.conf"
OPENVPN_SERVER_DIR = Path("/etc/openvpn/server")
ESSL_DIR = Path("/opt/essl")
ESSL_CERT_DIR = Path("/etc/ssl/eovpanel")


# ---------------------------------------------------------------------------
# OS / root detection
# ---------------------------------------------------------------------------

@dataclass
class OsInfo:
    distro: str          # "ubuntu", "debian", "centos", "fedora", "unsupported"
    version: str         # e.g. "22.04", "12"
    is_root: bool
    is_debian_like: bool


def detect_os() -> OsInfo:
    """Detect the running OS distribution and root status."""
    is_root = os.geteuid() == 0
    distro = "unsupported"
    version = ""
    is_debian_like = False

    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    distro = line.split("=", 1)[1].strip().strip('"').lower()
                elif line.startswith("VERSION_ID="):
                    version = line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass

    is_debian_like = distro in ("ubuntu", "debian")

    return OsInfo(
        distro=distro,
        version=version,
        is_root=is_root,
        is_debian_like=is_debian_like,
    )


# ---------------------------------------------------------------------------
# Public IP detection
# ---------------------------------------------------------------------------

def detect_public_ip() -> str:
    """Try to detect the server's public IP via external services."""
    services = [
        "http://ip1.dynupdate.no-ip.com/",
        "http://ifconfig.me",
        "http://icanhazip.com",
    ]
    for url in services:
        try:
            result = subprocess.run(
                ["curl", "-m", "5", "-4Ls", url],
                capture_output=True, text=True, timeout=10,
            )
            ip = result.stdout.strip()
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
                return ip
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    # Fallback: try to read from the default route interface
    try:
        result = subprocess.run(
            ["ip", "-4", "route", "get", "1.1.1.1"],
            capture_output=True, text=True, timeout=5,
        )
        match = re.search(r"src\s+([\d.]+)", result.stdout)
        if match:
            return match.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ""


# ---------------------------------------------------------------------------
# Network interface detection
# ---------------------------------------------------------------------------

def detect_default_interface() -> str:
    """Return the network interface used for the default route."""
    try:
        result = subprocess.run(
            ["ip", "-4", "route", "show", "default"],
            capture_output=True, text=True, timeout=5,
        )
        parts = result.stdout.strip().split()
        if "dev" in parts:
            idx = parts.index("dev")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "eth0"


# ---------------------------------------------------------------------------
# OpenVPN detection
# ---------------------------------------------------------------------------

def openvpn_installed() -> bool:
    """Check if OpenVPN is already installed on the host."""
    return shutil.which("openvpn") is not None or OPENVPN_SERVER_DIR.exists()


def docker_running() -> bool:
    """Check if Docker is installed and the daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def containers_running() -> list[str]:
    """Return names of running eovpanel containers."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=eovpanel", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


# ---------------------------------------------------------------------------
# ESSL (TLS) helpers
# ---------------------------------------------------------------------------

ESSL_SCRIPT_URL = "https://raw.githubusercontent.com/erfjab/ESSL/main/essl.sh"
ESSL_INSTALL_PATH = ESSL_DIR / "essl.sh"


def ensure_essl_installed() -> Path:
    """Download the ESSL script if not already present. Returns its path."""
    if ESSL_INSTALL_PATH.exists():
        return ESSL_INSTALL_PATH

    ESSL_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["curl", "-fsSL", ESSl_SCRIPT_URL, "-o", str(ESSL_INSTALL_PATH)],
        check=True, timeout=30,
    )
    ESSL_INSTALL_PATH.chmod(0o755)
    return ESSL_INSTALL_PATH


def run_essl(domain: str, email: str, dest_dir: Path) -> tuple[bool, str]:
    """Run ESSL non-interactively. Returns (success, output)."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        script = ensure_essl_installed()
        # ESSL is interactive; we pipe answers to it.
        # Based on the ESSL README, it accepts: domain, email, webroot
        input_text = f"{domain}\n{email}\n{dest_dir}\n"
        result = subprocess.run(
            ["bash", str(script)],
            input=input_text, capture_output=True, text=True, timeout=120,
        )
        output = result.stdout + result.stderr
        # Check if cert files were produced
        cert = dest_dir / "fullchain.pem"
        key = dest_dir / "privkey.pem"
        if cert.exists() and key.exists():
            return True, output
        return False, output
    except Exception as exc:
        return False, str(exc)


def configure_nginx_tls(cert_path: Path, key_path: Path) -> None:
    """Update the frontend nginx config to use TLS certificates."""
    nginx_conf = NGINX_CONF
    if not nginx_conf.exists():
        return

    content = nginx_conf.read_text(encoding="utf-8")

    # Remove existing SSL block if any
    content = re.sub(r"ssl_certificate .*;\n", "", content)
    content = re.sub(r"ssl_certificate_key .*;\n", "", content)
    content = re.sub(r"listen 443 ssl.*;\n", "", content)
    content = re.sub(r"ssl_protocols .*;\n", "", content)

    # Insert TLS config after the first listen line
    ssl_block = f"""
    listen 443 ssl;
    ssl_certificate {cert_path};
    ssl_certificate_key {key_path};
    ssl_protocols TLSv1.2 TLSv1.3;
"""
    content = content.replace("listen 80;", "listen 80;\n" + ssl_block, 1)

    nginx_conf.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# .env file helpers
# ---------------------------------------------------------------------------

def read_env(path: Path | None = None) -> dict[str, str]:
    """Parse a .env file into a dict."""
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
    """Write a dict as a .env file."""
    path = path or ENV_FILE
    lines = [f"{k}={v}" for k, v in data.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_env(updates: dict[str, str], path: Path | None = None) -> None:
    """Merge updates into an existing .env file, preserving comments."""
    path = path or ENV_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    keys_written = set()

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
# Subprocess streaming (for the TUI log pane)
# ---------------------------------------------------------------------------

async def stream_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    on_line: Callable[[str], None] | None = None,
    on_line_async: Callable[[str], asyncio.coroutine] | None = None,
) -> tuple[int, str]:
    """
    Run a command asynchronously, streaming stdout+stderr line by line.

    Calls on_line(line) for each line produced.  Returns (returncode, full_output).
    """
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
        env=merged_env,
    )

    output_lines: list[str] = []
    assert proc.stdout is not None

    async for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
        output_lines.append(line)
        if on_line:
            on_line(line)
        if on_line_async:
            await on_line_async(line)

    await proc.wait()
    return proc.returncode or 0, "\n".join(output_lines)


def run_command_sync(
    cmd: list[str],
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run a command synchronously, capturing all output."""
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, env=merged_env, timeout=600,
    )
    return result.returncode, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Seed / bootstrap helpers
# ---------------------------------------------------------------------------

def generate_jwt_secret() -> str:
    """Generate a cryptographically secure JWT secret."""
    return secrets.token_hex(32)


def seed_backend_admin(username: str, password: str) -> bool:
    """
    Seed the first sudo admin by setting env vars and restarting the backend.
    The backend's seed_all() reads SUDO_USERNAME / SUDO_PASSWORD on startup.
    """
    env = read_env()
    env["SUDO_USERNAME"] = username
    env["SUDO_PASSWORD"] = password
    env["JWT_SECRET_KEY"] = env.get("JWT_SECRET_KEY") or generate_jwt_secret()
    write_env(env)
    return True


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

async def docker_compose_up(
    on_line: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Run docker compose up -d from the repo's docker directory."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--build"]
    return await stream_command(cmd, cwd=str(DOCKER_DIR), on_line=on_line)


async def docker_compose_down(
    remove_volumes: bool = False,
    on_line: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Run docker compose down."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "down"]
    if remove_volumes:
        cmd.append("-v")
    return await stream_command(cmd, cwd=str(DOCKER_DIR), on_line=on_line)


async def docker_compose_restart(
    on_line: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Restart containers."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "restart"]
    return await stream_command(cmd, cwd=str(DOCKER_DIR), on_line=on_line)

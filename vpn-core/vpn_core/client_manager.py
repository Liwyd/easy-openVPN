"""
client_manager.py — Create, revoke, and list OpenVPN client certificates.

All functions operate on the easy-rsa PKI and OpenVPN server directory.
They shell out to the easy-rsa script for certificate operations and
parse the index.txt file for listing.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_SERVER_DIR = Path("/opt/eovpanel/vpn")
DEFAULT_EASYRSA_DIR = Path("/opt/eovpanel/vpn/easy-rsa")
DEFAULT_CLIENT_COMMON = DEFAULT_SERVER_DIR / "client-common.txt"
DEFAULT_CERT_DAYS = 3650


def _detect_public_ip(server_dir: Path) -> str:
    """Detect public IP from server.conf or external service."""
    server_conf = server_dir / "server.conf"
    try:
        with open(server_conf, encoding="utf-8") as f:
            for line in f:
                match = re.match(r"^\s*local\s+(\S+)", line)
                if match:
                    return match.group(1)
                match = re.match(r"^\s*remote\s+(\S+)\s+\d+", line)
                if match and match.group(1) not in ("0.0.0.0", "127.0.0.1"):
                    return match.group(1)
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(
            ["wget", "-T", "5", "-t", "1", "-4qO-", "http://ip1.dynupdate.no-ip.com/"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        result = subprocess.run(
            ["curl", "-m", "5", "-4Ls", "http://ip1.dynupdate.no-ip.com/"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_group_name() -> str:
    if os.path.exists("/etc/debian_version"):
        return "nogroup"
    return "nobody"


def _run_easyrsa(args: list[str], easyrsa_dir: Path) -> subprocess.CompletedProcess:
    """Run an easy-rsa command and return the result."""
    easyrsa = easyrsa_dir / "easyrsa"
    if not easyrsa.exists():
        raise FileNotFoundError(f"easyrsa script not found at {easyrsa}")

    cmd = [str(easyrsa), "--batch"] + args
    log.debug("Running: %s (cwd=%s)", " ".join(cmd), easyrsa_dir)
    result = subprocess.run(
        cmd,
        cwd=str(easyrsa_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        log.error("easy-rsa failed: %s\nstdout: %s\nstderr: %s",
                  " ".join(cmd), result.stdout, result.stderr)
        raise RuntimeError(f"easy-rsa command failed: {result.stderr.strip()}")
    return result


def _sanitise_name(name: str) -> str:
    """Sanitise a client name to only allow safe characters."""
    return re.sub(r"[^0-9a-zA-Z_-]", "_", name)


def _generate_ovpn(
    client_name: str,
    server_dir: Path,
    public_ip: str,
    protocol: str,
    port: int,
    cipher: str = "AES-256-GCM",
    auth: str = "SHA256",
    tls_mode: str = "tls-crypt",
) -> str:
    """Build a complete .ovpn profile file with inline certificates.

    Reads the current cipher, auth, and TLS mode from the DB (passed as
    parameters) instead of relying on the stale client-common.txt template.
    This ensures subscription links always serve the latest config.
    """
    # If public_ip is empty, try to detect it from server.conf or network
    if not public_ip:
        public_ip = _detect_public_ip(server_dir)

    # Build the base config dynamically from current settings
    lines = [
        "client",
        "dev tun",
        f"proto {protocol}",
        f"remote {public_ip} {port}",
        "resolv-retry infinite",
        "nobind",
        "persist-key",
        "persist-tun",
        "remote-cert-tls server",
        f"cipher {cipher}",
        f"auth {auth}",
    ]
    if tls_mode == "tls-crypt":
        lines.append("tls-crypt")
    elif tls_mode == "tls-auth":
        lines.append("tls-auth")
    lines.append("ignore-unknown-option block-outside-dns")
    lines.append("verb 3")

    base = "\n".join(lines)

    # Read CA certificate
    ca_cert = (server_dir / "ca.crt").read_text(encoding="utf-8").strip()

    # Read client certificate
    pki_issued = server_dir / "easy-rsa" / "pki" / "issued" / f"{client_name}.crt"
    # Strip header/footer, keep only the base64 block
    cert_lines = []
    in_cert = False
    for line in pki_issued.read_text(encoding="utf-8").splitlines():
        if "-----BEGIN CERTIFICATE-----" in line:
            in_cert = True
        if in_cert:
            cert_lines.append(line)
        if "-----END CERTIFICATE-----" in line:
            in_cert = False
    client_cert = "\n".join(cert_lines)

    # Read client private key
    pki_private = server_dir / "easy-rsa" / "pki" / "private" / f"{client_name}.key"
    client_key = pki_private.read_text(encoding="utf-8").strip()

    # Read TLS key (only if needed)
    ovpn = base + "\n"
    ovpn += f"<ca>\n{ca_cert}\n</ca>\n"
    ovpn += f"<cert>\n{client_cert}\n</cert>\n"
    ovpn += f"<key>\n{client_key}\n</key>\n"

    if tls_mode == "tls-crypt":
        tc_key = (server_dir / "tc.key").read_text(encoding="utf-8").strip()
        ovpn += f"<tls-crypt>\n{tc_key}\n</tls-crypt>\n"
    elif tls_mode == "tls-auth":
        ta_key = (server_dir / "ta.key").read_text(encoding="utf-8").strip()
        ovpn += f"<tls-auth>\n{ta_key}\n</tls-auth>\n"

    return ovpn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class ClientInfo:
    """Information about a listed client."""
    common_name: str
    status: str  # "V" (valid) or "R" (revoked)
    expiry_date: str  # YYMMDDHHMMSSZ
    serial_number: str
    filename: str | None = None


def create_client(
    common_name: str,
    server_dir: Path | str = DEFAULT_SERVER_DIR,
    easyrsa_dir: Path | str = DEFAULT_EASYRSA_DIR,
    public_ip: str = "",
    protocol: str = "udp",
    port: int = 1194,
    cipher: str = "AES-256-GCM",
    auth: str = "SHA256",
    tls_mode: str = "tls-crypt",
) -> str:
    """
    Generate a client key/cert via easy-rsa and return the .ovpn file content.

    Raises FileExistsError if the client certificate already exists.
    Raises RuntimeError on easy-rsa failure.
    """
    common_name = _sanitise_name(common_name)
    if not common_name:
        raise ValueError("Client name is empty after sanitisation.")

    server_dir = Path(server_dir)
    easyrsa_dir = Path(easyrsa_dir)

    # Check if cert already exists
    cert_path = easyrsa_dir / "pki" / "issued" / f"{common_name}.crt"
    if cert_path.exists():
        raise FileExistsError(f"Client '{common_name}' already has a certificate.")

    log.info("Creating client certificate for '%s'...", common_name)

    # Build client certificate
    _run_easyrsa(
        [f"--days={DEFAULT_CERT_DAYS}", "build-client-full", common_name, "nopass"],
        easyrsa_dir,
    )

    log.info("Client certificate for '%s' created.", common_name)

    # Generate .ovpn profile
    ovpn_content = _generate_ovpn(
        common_name,
        server_dir,
        public_ip,
        protocol,
        port,
        cipher=cipher,
        auth=auth,
        tls_mode=tls_mode,
    )

    return ovpn_content


def revoke_client(
    common_name: str,
    easyrsa_dir: Path | str = DEFAULT_EASYRSA_DIR,
    server_dir: Path | str = DEFAULT_SERVER_DIR,
) -> None:
    """
    Revoke a client certificate via easy-rsa and update the CRL.

    Raises FileNotFoundError if the client doesn't exist.
    Raises RuntimeError on easy-rsa failure.
    """
    common_name = _sanitise_name(common_name)
    easyrsa_dir = Path(easyrsa_dir)
    server_dir = Path(server_dir)

    # Check that the cert exists and is valid
    cert_path = easyrsa_dir / "pki" / "issued" / f"{common_name}.crt"
    if not cert_path.exists():
        raise FileNotFoundError(f"No certificate found for client '{common_name}'.")

    log.info("Revoking client certificate for '%s'...", common_name)

    # Revoke
    _run_easyrsa(["revoke", common_name], easyrsa_dir)

    # Regenerate CRL
    _run_easyrsa(["--days=DEFAULT_CERT_DAYS", "gen-crl"], easyrsa_dir)

    # Copy CRL to server dir
    crl_src = easyrsa_dir / "pki" / "crl.pem"
    crl_dst = server_dir / "crl.pem"
    shutil.copy2(crl_src, crl_dst)

    # Fix permissions (OpenVPN reads CRL as nobody)
    group = _get_group_name()
    shutil.chown(crl_dst, user="nobody", group=group)

    # Clean up cert artifacts
    req_path = easyrsa_dir / "pki" / "reqs" / f"{common_name}.req"
    key_path = easyrsa_dir / "pki" / "private" / f"{common_name}.key"
    if req_path.exists():
        req_path.unlink()
    if key_path.exists():
        key_path.unlink()

    log.info("Client '%s' revoked. CRL updated.", common_name)


def list_clients(
    easyrsa_dir: Path | str = DEFAULT_EASYRSA_DIR,
) -> list[ClientInfo]:
    """
    Parse the easy-rsa index.txt to list all clients (valid and revoked).

    Returns a list of ClientInfo dataclass instances.
    """
    easyrsa_dir = Path(easyrsa_dir)
    index_txt = easyrsa_dir / "pki" / "index.txt"

    if not index_txt.exists():
        log.warning("index.txt not found at %s", index_txt)
        return []

    clients: list[ClientInfo] = []

    for line in index_txt.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue

        # Format: STATUS SERIAL EXPIRY DN FILENAME
        # e.g.:   V       2E...   250101120000Z    /CN=client1    client1.crt
        status = parts[0]
        serial = parts[1]
        expiry = parts[2]

        # Extract CN from DN
        cn_match = re.search(r"/CN=(\S+)", line)
        if cn_match:
            cn = cn_match.group(1)
        else:
            cn = parts[3].split("=")[-1] if "=" in parts[3] else parts[3]

        filename = parts[-1] if len(parts) > 4 else None

        clients.append(ClientInfo(
            common_name=cn,
            status=status,
            expiry_date=expiry,
            serial_number=serial,
            filename=filename,
        ))

    return clients

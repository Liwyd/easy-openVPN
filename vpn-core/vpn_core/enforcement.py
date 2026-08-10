"""
enforcement.py — Kill, disable, and enable OpenVPN clients without full revocation.

- kill_client_session: sends `kill <CN>` via the management interface
- disable_client: writes a CCD file that restricts the client
- enable_client: removes the CCD restriction

These are callable by the backend's scheduler when a quota/expiry/time-window
is hit, without needing to revoke the cert permanently.
"""

from __future__ import annotations

import logging
import os
import socket
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_MANAGEMENT_SOCKET = "/run/openvpn/management.sock"
DEFAULT_CCD_DIR = "/opt/eovpanel/vpn/ccd"
DEFAULT_TIMEOUT_SECONDS = 5


# ---------------------------------------------------------------------------
# Management interface helper
# ---------------------------------------------------------------------------

def _send_management_command(
    command: str,
    management_socket: str = DEFAULT_MANAGEMENT_SOCKET,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """
    Send a command to the OpenVPN management interface and return the response.
    """
    if ":" in management_socket and not management_socket.startswith("/"):
        host, port_str = management_socket.rsplit(":", 1)
        addr_info = socket.getaddrinfo(host, int(port_str), socket.AF_INET, socket.SOCK_STREAM)
        sock = socket.socket(addr_info[0][0], addr_info[0][1])
    else:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    sock.settimeout(timeout)
    try:
        sock.connect(management_socket)
        # Read welcome line
        _recv_until(sock, b"\n")

        # Send command
        sock.sendall((command + "\n").encode("utf-8"))

        # Read until END or SUCCESS
        data = _recv_until(sock, b"END\n", b"SUCCESS\n")
        return data.decode("utf-8", errors="replace")
    finally:
        sock.close()


def _recv_until(
    sock: socket.socket,
    *delimiters: bytes,
    max_bytes: int = 65536,
) -> bytes:
    """Read from socket until any delimiter is found."""
    buf = b""
    while len(buf) < max_bytes:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
        for delim in delimiters:
            if delim in buf:
                return buf
    return buf


# ---------------------------------------------------------------------------
# Kill session
# ---------------------------------------------------------------------------

def kill_client_session(
    common_name: str,
    management_socket: str = DEFAULT_MANAGEMENT_SOCKET,
) -> bool:
    """
    Kill the active session for the given client via the management interface.

    This does NOT revoke the certificate — the client can reconnect later.
    Used when a quota/expiry/time-window is hit.

    Returns True if the kill command was sent successfully.
    """
    try:
        response = _send_management_command(
            f"kill {common_name}",
            management_socket,
        )
        # The management interface responds with:
        #   SUCCESS: common-name <CN> terminated
        #   ERROR: common-name <CN> not found
        if "SUCCESS" in response:
            log.info("Killed session for client '%s'.", common_name)
            return True
        elif "not found" in response:
            log.info("Client '%s' is not currently connected.", common_name)
            return True  # Not an error — client is simply not online
        else:
            log.warning("Unexpected kill response for '%s': %s", common_name, response)
            return False
    except (ConnectionRefusedError, FileNotFoundError, OSError) as exc:
        log.error("Failed to connect to management interface: %s", exc)
        return False
    except socket.timeout:
        log.error("Management interface timed out while killing '%s'.", common_name)
        return False


# ---------------------------------------------------------------------------
# Disable / Enable via CCD
# ---------------------------------------------------------------------------

def _ensure_ccd_dir(ccd_dir: str | Path) -> Path:
    """Ensure the CCD directory exists and return it as a Path."""
    ccd = Path(ccd_dir)
    ccd.mkdir(parents=True, exist_ok=True)
    return ccd


def disable_client(
    common_name: str,
    ccd_dir: str | Path = DEFAULT_CCD_DIR,
    management_socket: str = DEFAULT_MANAGEMENT_SOCKET,
) -> bool:
    """
    Disable a client by writing a CCD file with a restrictive config.

    The CCD file contains a `disable` directive which tells OpenVPN to
    reject connections from this client.  The client can reconnect once
    the CCD file is removed or replaced.

    Also kills any active session for the client.

    Returns True on success.
    """
    ccd = _ensure_ccd_dir(ccd_dir)
    ccd_file = ccd / common_name

    try:
        # Write a CCD file that disables the client
        # OpenVPN doesn't have a native "disable" directive in CCD.
        # Instead, we use a combination of:
        # - push-restart to force a re-auth
        # - iroute to a dead network, effectively blackholing traffic
        # The simplest reliable approach: push a disconnect via management
        # and write a marker file that the connect hook checks.
        #
        # Actually, the most robust approach for CCD-based disable is to
        # use `disable` if available, or fall back to pushing a disconnect.
        # OpenVPN 2.5+ supports `disable` in CCD.
        ccd_file.write_text(
            "# This client is disabled by eovpanel.\n"
            "# Remove this file or edit CCD to re-enable.\n"
            "disable\n",
            encoding="utf-8",
        )
        log.info("Wrote CCD disable file for '%s' at %s", common_name, ccd_file)

        # Kill any active session
        kill_client_session(common_name, management_socket)

        return True
    except OSError as exc:
        log.error("Failed to write CCD file for '%s': %s", common_name, exc)
        return False


def enable_client(
    common_name: str,
    ccd_dir: str | Path = DEFAULT_CCD_DIR,
) -> bool:
    """
    Re-enable a disabled client by removing the CCD file.

    Returns True on success, False if the CCD file couldn't be removed.
    """
    ccd = Path(ccd_dir)
    ccd_file = ccd / common_name

    if not ccd_file.exists():
        log.info("No CCD file found for '%s', client is already enabled.", common_name)
        return True

    try:
        ccd_file.unlink()
        log.info("Removed CCD file for '%s', client is now enabled.", common_name)
        return True
    except OSError as exc:
        log.error("Failed to remove CCD file for '%s': %s", common_name, exc)
        return False


def is_client_disabled(
    common_name: str,
    ccd_dir: str | Path = DEFAULT_CCD_DIR,
) -> bool:
    """
    Check if a client is disabled (has a CCD file with 'disable' directive).
    """
    ccd = Path(ccd_dir)
    ccd_file = ccd / common_name

    if not ccd_file.exists():
        return False

    try:
        content = ccd_file.read_text(encoding="utf-8")
        return "disable" in content
    except OSError:
        return False

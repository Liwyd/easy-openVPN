"""
status_reader.py — Parse live client list from the OpenVPN management interface.

Connects to the management interface (unix socket or TCP) and issues the
`status 2` command to retrieve per-client byte counters and connection info.

Handles connection errors gracefully — if the management socket is
temporarily unreachable, returns an empty list and logs a warning.
"""

from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_MANAGEMENT_SOCKET = "/run/openvpn/management.sock"
DEFAULT_TIMEOUT_SECONDS = 5


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ClientStatus:
    """Live status of a single connected client."""
    common_name: str
    real_address: str
    bytes_received: int
    bytes_sent: int
    connected_since: str  # ISO-ish timestamp from OpenVPN


# ---------------------------------------------------------------------------
# Management interface communication
# ---------------------------------------------------------------------------

def _send_command(
    command: str,
    management_socket: str = DEFAULT_MANAGEMENT_SOCKET,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """
    Send a command to the OpenVPN management interface and return the response.

    Supports both unix sockets and TCP (host:port).
    """
    # Determine socket type
    if ":" in management_socket and not management_socket.startswith("/"):
        # TCP socket: host:port
        host, port_str = management_socket.rsplit(":", 1)
        addr_info = socket.getaddrinfo(host, int(port_str), socket.AF_INET, socket.SOCK_STREAM)
        sock = socket.socket(addr_info[0][0], addr_info[0][1])
    else:
        # Unix socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    sock.settimeout(timeout)
    try:
        sock.connect(management_socket)
        # Read the welcome/banner line
        _recv_until(sock, b"\n")

        # Send command
        sock.sendall((command + "\n").encode("utf-8"))

        # Read response until END marker
        data = _recv_until(sock, b"END\n")
        return data.decode("utf-8", errors="replace")
    finally:
        sock.close()


def _recv_until(sock: socket.socket, delimiter: bytes, max_bytes: int = 1048576) -> bytes:
    """Read from socket until delimiter is found or max_bytes reached."""
    buf = b""
    while len(buf) < max_bytes:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
        if delimiter in buf:
            # Return everything up to and including the delimiter
            idx = buf.index(delender) + len(delimiter)
            return buf[:idx]
    return buf


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_live_status(
    management_socket: str = DEFAULT_MANAGEMENT_SOCKET,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[ClientStatus]:
    """
    Connect to the management interface and return the list of live clients.

    Returns an empty list if the management socket is unreachable or
    if no clients are connected.
    """
    try:
        response = _send_command("status 2", management_socket, timeout)
    except (ConnectionRefusedError, FileNotFoundError, OSError) as exc:
        log.warning("Management interface unreachable at %s: %s", management_socket, exc)
        return []
    except socket.timeout:
        log.warning("Management interface timed out at %s", management_socket)
        return []

    return _parse_status(response)


def _parse_status(raw: str) -> list[ClientStatus]:
    """
    Parse the output of `status 2` from the management interface.

    The status 2 format has sections separated by blank lines.
    We look for the "Virtual Address" section which contains:
        Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since, ...
    """
    clients: list[ClientStatus] = []

    # Split into lines
    lines = raw.splitlines()

    # Find the "Virtual Address" section header
    in_section = False
    header_seen = False

    for line in lines:
        stripped = line.strip()

        # Section headers look like: "Virtual Address Table" or "ROUTING TABLE"
        if "Virtual Address" in stripped and "Table" in stripped:
            in_section = True
            header_seen = False
            continue

        if in_section:
            # Skip the column header line (Common Name,Real Address,...)
            if not header_seen and "Common Name" in stripped:
                header_seen = True
                continue

            # Empty line or section separator
            if not stripped:
                if header_seen:
                    # End of section
                    break
                continue

            # Parse data line
            # Format: CN,RealAddress,BytesReceived,BytesSent,ConnectedSince,...
            parts = stripped.split(",")
            if len(parts) >= 5:
                clients.append(ClientStatus(
                    common_name=parts[0].strip(),
                    real_address=parts[1].strip(),
                    bytes_received=_safe_int(parts[2]),
                    bytes_sent=_safe_int(parts[3]),
                    connected_since=parts[4].strip(),
                ))

    return clients


def _safe_int(value: str) -> int:
    """Parse an integer, returning 0 on failure."""
    try:
        return int(value.strip())
    except (ValueError, TypeError):
        return 0

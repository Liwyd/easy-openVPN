"""
status_reader.py — Parse live client list from the OpenVPN management interface.

Connects to the management interface (unix socket or TCP) and issues the
`status 2` command to retrieve per-client byte counters and connection info.

Handles connection errors gracefully — if the management socket is
temporarily unreachable, returns an empty list and logs a warning.
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass

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
            idx = buf.index(delimiter) + len(delimiter)
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

    The status 2 format is line-based with a tag prefix on every line
    (TITLE, TIME, HEADER, CLIENT_LIST, ROUTING_TABLE, GLOBAL_STATS).
    The per-client byte counters live in the CLIENT_LIST rows; the
    HEADER,CLIENT_LIST line declares the column names, so we map them
    positionally instead of assuming a fixed layout.  This stays
    correct across OpenVPN versions (e.g. 2.3 omits the Virtual IPv6
    Address column that 2.4+ includes).
    """
    clients: list[ClientStatus] = []

    # Column name -> data-row index, derived from HEADER,CLIENT_LIST.
    # A data row has one fewer leading tag than its header line, so
    # column names starting at header index 2 land at data index 1.
    columns: dict[str, int] = {}

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        parts = stripped.split(",")
        tag = parts[0]

        # HEADER,CLIENT_LIST,<col names...> declares the CLIENT_LIST layout
        if tag == "HEADER" and len(parts) > 2 and parts[1] == "CLIENT_LIST":
            columns = {name: idx + 1 for idx, name in enumerate(parts[2:])}
            continue

        # Data rows carry: CLIENT_LIST,Common Name,Real Address,...
        if tag == "CLIENT_LIST" and columns:
            common_name = _column(parts, columns, "Common Name")
            if not common_name:
                continue
            # Skip malformed rows that don't span the byte-counter columns
            if not _row_complete(parts, columns):
                continue
            clients.append(ClientStatus(
                common_name=common_name,
                real_address=_column(parts, columns, "Real Address"),
                bytes_received=_safe_int(_column(parts, columns, "Bytes Received")),
                bytes_sent=_safe_int(_column(parts, columns, "Bytes Sent")),
                connected_since=_column(parts, columns, "Connected Since"),
            ))

    return clients


def _column(parts: list[str], columns: dict[str, int], name: str) -> str:
    """Extract a named column from a CLIENT_LIST data row, or '' if absent."""
    idx = columns.get(name)
    if idx is None or idx >= len(parts):
        return ""
    return parts[idx].strip()


def _row_complete(parts: list[str], columns: dict[str, int]) -> bool:
    """Return True if a data row spans all columns we read.

    A malformed/truncated row (e.g. a partial read) would otherwise
    parse into zeroed byte counters and corrupt a user's usage totals.
    """
    for name in ("Common Name", "Real Address", "Bytes Received", "Bytes Sent", "Connected Since"):
        idx = columns.get(name)
        if idx is None or idx >= len(parts):
            return False
    return True


def _safe_int(value: str) -> int:
    """Parse an integer, returning 0 on failure."""
    try:
        return int(value.strip())
    except (ValueError, TypeError):
        return 0

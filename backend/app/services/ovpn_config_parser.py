"""Parse an OpenVPN server config file and extract known settings.

Reads the file line by line, strips comments and blank lines, and uses
one regex per directive.  Unknown lines are silently ignored.  Every
extracted value is validated against the same enum/range rules the
manual settings form uses; values that fail validation are reported but
not applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.server_config import AuthDigest, Cipher, Protocol  # noqa: I001


# ---------------------------------------------------------------------------
# Allowed value sets (mirrors the frontend / schema validation)
# ---------------------------------------------------------------------------

_VALID_PROTOCOLS = {p.value for p in Protocol}
_VALID_CIPHERS = {c.value for c in Cipher}
_VALID_AUTH = {a.value for a in AuthDigest}

_MAX_PORT = 65535
_MIN_MTU = 576
_MAX_MTU = 65535


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class FieldResult:
    field_name: str
    current: Any
    parsed: Any
    status: str  # "ok" | "same" | "invalid"
    reason: str = ""


@dataclass
class ImportPreview:
    fields: list[FieldResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-directive parsers
# ---------------------------------------------------------------------------

def _parse_protocol(raw: str) -> tuple[Any, str]:
    val = raw.strip().lower()
    if val not in _VALID_PROTOCOLS:
        return None, f"Unsupported protocol: {val}"
    return val, ""


def _parse_port(raw: str) -> tuple[Any, str]:
    try:
        val = int(raw.strip())
    except ValueError:
        return None, "Not a valid port number"
    if val < 1 or val > _MAX_PORT:
        return None, f"Port out of range (1-{_MAX_PORT})"
    return val, ""


def _parse_cipher(raw: str) -> tuple[Any, str]:
    val = raw.strip()
    if val not in _VALID_CIPHERS:
        return None, f"Unsupported cipher: {val}"
    return val, ""


def _parse_auth_digest(raw: str) -> tuple[Any, str]:
    val = raw.strip().upper()
    if val not in _VALID_AUTH:
        return None, f"Unsupported auth digest: {val}"
    return val, ""


def _parse_interface(raw: str) -> tuple[Any, str]:
    val = raw.strip()
    dev = re.match(r"^(tun|tap)", val, re.IGNORECASE)
    if not dev:
        return None, f"Unsupported dev type: {val}"
    return dev.group(0).lower(), ""


def _parse_mtu(raw: str) -> tuple[Any, str]:
    try:
        val = int(raw.strip())
    except ValueError:
        return None, "Not a valid MTU"
    if val < _MIN_MTU or val > _MAX_MTU:
        return None, f"MTU out of range ({_MIN_MTU}-{_MAX_MTU})"
    return val, ""


def _parse_keepalive(raw: str) -> tuple[tuple[int, int] | None, str]:
    parts = raw.strip().split()
    if len(parts) != 2:
        return None, "Expected two integers (interval timeout)"
    try:
        interval, timeout = int(parts[0]), int(parts[1])
    except ValueError:
        return None, "keepalive values must be integers"
    if interval < 1 or timeout < 1:
        return None, "keepalive values must be positive"
    return (interval, timeout), ""


def _parse_dns_ip(raw: str) -> tuple[str | None, str]:
    val = raw.strip()
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", val):
        return None, f"Not a valid IPv4 address: {val}"
    return val, ""


def _parse_bool_flag(_raw: str = "") -> tuple[bool, str]:
    return True, ""


# ---------------------------------------------------------------------------
# Directive registry — one entry per recognised directive
# ---------------------------------------------------------------------------

_DIRECTIVES: list[tuple[str, re.Pattern[str], str, Any]] = [
    # (field_name, regex, parser_name, default_if_absent)
    ("protocol",          re.compile(r"^\s*proto\s+(udp6?|tcp6?)\s*$", re.I),        "_parse_protocol",      None),
    ("port",              re.compile(r"^\s*port\s+(\d+)\s*$"),                        "_parse_port",          None),
    ("cipher",            re.compile(r"^\s*cipher\s+([\w-]+)\s*$"),                   "_parse_cipher",        None),
    ("auth_digest",       re.compile(r"^\s*auth\s+([\w-]+)\s*$"),                     "_parse_auth_digest",   None),
    ("interface",         re.compile(r"^\s*dev\s+(tun|tap)\d*\s*$", re.I),           "_parse_interface",     None),
    ("mtu",               re.compile(r"^\s*(?:tun-mtu|mtu)\s+(\d+)\s*$"),             "_parse_mtu",           None),
    ("client_to_client",  re.compile(r"^\s*client-to-client\s*$"),                    "_parse_bool_flag",     None),
    ("redirect_gateway",  re.compile(r"^\s*push\s+\"redirect-gateway[^\"]*\""),       "_parse_bool_flag",     None),
]

# Two directives share the same parser but need special collection:
# tls_mode (tls-crypt / tls-auth presence)
_TLS_CRYPT = re.compile(r"^\s*tls-crypt\s+\S+\s*$")
_TLS_AUTH  = re.compile(r"^\s*tls-auth\s+\S+")
_DNS_DIRECTIVE = re.compile(
    r"^\s*push\s+\"dhcp-option\s+DNS\s+([\d.]+)\"", re.I
)
# remote is used only to suggest public_host
_REMOTE_RE = re.compile(r"^\s*remote\s+(\S+)\s*(\d+)?\s*$")

_PARSER_MAP: dict[str, Any] = {d[2]: globals()[d[2]] for d in _DIRECTIVES}


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_ovpn_config(content: str, current_config: dict[str, Any]) -> ImportPreview:
    """Parse *content* (raw file text) and return an ImportPreview.

    *current_config* is a dict of the current DB values so we can
    report "same" / "different".
    """
    parsed_values: dict[str, Any] = {}
    tls_found: str | None = None
    dns_list: list[str] = []
    remote_host: str | None = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        # Strip inline comments (only outside quotes)
        if not line or line.startswith("#") or line.startswith(";"):
            continue

        # --- TLS mode (special: not stored as a directive entry) ----------
        if _TLS_CRYPT.match(line):
            tls_found = "tls-crypt"
            continue
        if _TLS_AUTH.match(line):
            tls_found = "tls-auth"
            continue

        # --- DNS lines (accumulate) ---------------------------------------
        m = _DNS_DIRECTIVE.match(line)
        if m:
            ip, _err = _parse_dns_ip(m.group(1))
            if ip:
                dns_list.append(ip)
            continue

        # --- remote (used only to suggest public_host) --------------------
        m = _REMOTE_RE.match(line)
        if m:
            remote_host = m.group(1)
            continue

        # --- Generic directives -------------------------------------------
        for field_name, regex, parser_name, _default in _DIRECTIVES:
            m = regex.match(line)
            if m:
                parser = _PARSER_MAP[parser_name]
                # Pass captured groups (single string or empty)
                arg = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
                val, err = parser(arg)
                if err:
                    # Store as invalid placeholder
                    parsed_values[field_name] = ("__invalid__", err)
                else:
                    parsed_values[field_name] = val
                break
        # Unknown directives → ignored silently

    # --- Build the result list -------------------------------------------
    preview = ImportPreview()
    seen_fields: set[str] = set()

    def _add(field_name: str, parsed: Any) -> None:
        if field_name in seen_fields:
            return
        seen_fields.add(field_name)
        current = current_config.get(field_name)

        if parsed is None:
            return  # not found in file

        if isinstance(parsed, tuple) and parsed[0] == "__invalid__":
            preview.fields.append(FieldResult(
                field_name=field_name,
                current=current,
                parsed=None,
                status="invalid",
                reason=parsed[1],
            ))
            return

        # For booleans that were not in the file, don't add them
        if parsed is None:
            return

        if parsed == current:
            preview.fields.append(FieldResult(
                field_name=field_name,
                current=current,
                parsed=parsed,
                status="same",
            ))
        else:
            preview.fields.append(FieldResult(
                field_name=field_name,
                current=current,
                parsed=parsed,
                status="ok",
            ))

    # Add each parsed directive
    for field_name, val in parsed_values.items():
        _add(field_name, val)

    # TLS mode
    if tls_found:
        _add("tls_mode", tls_found)

    # DNS servers
    if dns_list:
        _add("dns_servers", dns_list)

    # remote → suggest public_host (only if different, do NOT silently apply)
    if remote_host:
        _add("public_host", remote_host)

    return preview


def preview_to_dict(preview: ImportPreview) -> dict[str, Any]:
    """Convert an ImportPreview to a JSON-serialisable dict."""
    return {
        "fields": [
            {
                "field": f.field_name,
                "current": f.current,
                "parsed": f.parsed,
                "status": f.status,
                "reason": f.reason,
            }
            for f in preview.fields
        ]
    }

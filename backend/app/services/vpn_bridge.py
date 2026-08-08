"""VPN bridge — thin wrapper around vpn-core for testability.

All backend → vpn-core calls go through this module so tests can mock
a single import path.  Functions here add error handling, logging, and
convert vpn-core exceptions into clean return values.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def create_client_cert(
    common_name: str,
    server_dir: str = "/etc/openvpn/server",
    easyrsa_dir: str = "/etc/openvpn/easy-rsa",
    public_ip: str = "",
    protocol: str = "udp",
    port: int = 1194,
) -> str:
    """Create a client certificate and return the .ovpn content.

    Raises RuntimeError or FileExistsError on failure — callers must
    handle these and roll back any DB state.
    """
    from vpn_core.client_manager import create_client

    return create_client(
        common_name=common_name,
        server_dir=Path(server_dir),
        easyrsa_dir=Path(easyrsa_dir),
        public_ip=public_ip,
        protocol=protocol,
        port=port,
    )


def revoke_client_cert(
    common_name: str,
    easyrsa_dir: str = "/etc/openvpn/easy-rsa",
    server_dir: str = "/etc/openvpn/server",
) -> None:
    """Revoke a client certificate.  Raises on failure."""
    from vpn_core.client_manager import revoke_client

    revoke_client(
        common_name=common_name,
        easyrsa_dir=Path(easyrsa_dir),
        server_dir=Path(server_dir),
    )


def get_live_status(
    management_socket: str = "/run/openvpn/management.sock",
) -> list[dict]:
    """Get live client status from the management interface.

    Returns a list of dicts with keys: common_name, real_address,
    bytes_received, bytes_sent, connected_since.  Returns empty list
    on connection failure.
    """
    from vpn_core.status_reader import get_live_status as _get_live_status

    clients = _get_live_status(management_socket=management_socket)
    return [
        {
            "common_name": c.common_name,
            "real_address": c.real_address,
            "bytes_received": c.bytes_received,
            "bytes_sent": c.bytes_sent,
            "connected_since": c.connected_since,
        }
        for c in clients
    ]


def kill_client_session(
    common_name: str,
    management_socket: str = "/run/openvpn/management.sock",
) -> bool:
    """Kill a client's active session.  Returns True on success."""
    from vpn_core.enforcement import kill_client_session as _kill

    return _kill(common_name=common_name, management_socket=management_socket)


def disable_client(
    common_name: str,
    ccd_dir: str = "/etc/openvpn/server/ccd",
    management_socket: str = "/run/openvpn/management.sock",
) -> bool:
    """Disable a client via CCD.  Returns True on success."""
    from vpn_core.enforcement import disable_client as _disable

    return _disable(
        common_name=common_name,
        ccd_dir=ccd_dir,
        management_socket=management_socket,
    )


def enable_client(
    common_name: str,
    ccd_dir: str = "/etc/openvpn/server/ccd",
) -> bool:
    """Re-enable a client by removing the CCD file.  Returns True on success."""
    from vpn_core.enforcement import enable_client as _enable

    return _enable(common_name=common_name, ccd_dir=ccd_dir)


def generate_ovpn_file(
    common_name: str,
    server_dir: str = "/etc/openvpn/server",
    public_ip: str = "",
    protocol: str = "udp",
    port: int = 1194,
) -> str:
    """Render the .ovpn file for an existing client without re-creating the cert.

    Falls back to reading the existing client-common.txt + cert/key if the
    cert already exists.  This is used by the /config and /sub endpoints.
    """
    from vpn_core.client_manager import _generate_ovpn

    return _generate_ovpn(
        client_name=common_name,
        server_dir=Path(server_dir),
        public_ip=public_ip,
        protocol=protocol,
        port=port,
    )


def apply_server_config(
    protocol: str = "udp",
    port: int = 1194,
    interface: str = "tun0",
    cipher: str = "AES-256-GCM",
    auth: str = "SHA256",
    dns_servers: list[str] | None = None,
    mtu: int | None = None,
    keepalive_interval: int = 10,
    keepalive_timeout: int = 120,
    client_to_client: bool = False,
    redirect_gateway: bool = True,
    public_ip: str = "",
    tls_crypt: bool = True,
    tls_auth: bool = False,
    management_socket: str = "/run/openvpn/management.sock",
    ccd_dir: str = "/etc/openvpn/server/ccd",
    hooks_dir: str = "/etc/openvpn/server/hooks",
) -> bool:
    """Apply server configuration via vpn-core.  Returns True on success."""
    from vpn_core.config_writer import ServerConfigRow
    from vpn_core.config_writer import apply_server_config as _apply

    cfg = ServerConfigRow(
        protocol=protocol,
        port=port,
        interface=interface,
        cipher=cipher,
        auth=auth,
        dns_servers=dns_servers,
        mtu=mtu,
        keepalive_interval=keepalive_interval,
        keepalive_timeout=keepalive_timeout,
        client_to_client=client_to_client,
        redirect_gateway=redirect_gateway,
        public_ip=public_ip,
        tls_crypt=tls_crypt,
        tls_auth=tls_auth,
        management_socket=management_socket,
        ccd_dir=ccd_dir,
        hooks_dir=hooks_dir,
    )
    return _apply(cfg)

"""
vpn_core — OpenVPN helper functions.

This package wraps easy-rsa operations and OpenVPN config generation.
Logic adapted from Nyr's openvpn-install script (MIT license).
https://github.com/Nyr/openvpn-install

Modules:
    setup_server      – Idempotent OpenVPN + easy-rsa server bootstrap
    config_writer     – Render ServerConfig DB row -> server.conf, apply it
    client_manager    – Create/revoke/list client certificates
    status_reader     – Parse live client list from management interface
    enforcement       – Kill/disable/enable clients without full revocation
"""

from vpn_core.config_writer import render_server_conf, apply_server_config
from vpn_core.client_manager import create_client, revoke_client, list_clients
from vpn_core.status_reader import get_live_status
from vpn_core.enforcement import kill_client_session, disable_client, enable_client

__all__ = [
    "render_server_conf",
    "apply_server_config",
    "create_client",
    "revoke_client",
    "list_clients",
    "get_live_status",
    "kill_client_session",
    "disable_client",
    "enable_client",
]

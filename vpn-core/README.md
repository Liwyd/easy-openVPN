# vpn-core

Python helpers that wrap easy-rsa and OpenVPN configuration generation.

This module contains logic adapted from [Nyr's openvpn-install script](https://github.com/Nyr/openvpn-install).

## License Notice

The original openvpn-install script by Nyr is licensed under MIT.
See: https://github.com/Nyr/openvpn-install/blob/master/LICENSE

Portions of the logic in this directory are adapted from that script and
retain the original MIT license.

## Deployment Model

vpn-core runs on the **host** (not inside Docker). The backend container
accesses vpn-core functions via direct Python imports — both run in the
same process/container.

### Host Paths

OpenVPN and easy-rsa are installed on the host at:

| Path | Description |
|------|-------------|
| `/etc/openvpn/server/` | OpenVPN config, certs, CRL, management socket |
| `/etc/openvpn/server/easy-rsa/` | easy-rsa PKI directory |
| `/etc/openvpn/server/ccd/` | Client-config-dir (per-client overrides) |
| `/etc/openvpn/server/hooks/` | Connect/disconnect hook scripts |
| `/etc/openvpn/server/state/` | Runtime state files (expiry, quotas) |
| `/run/openvpn/management.sock` | Unix socket for management interface |

### Docker Volume Mounts

The backend container mounts these host paths via docker-compose:

```yaml
volumes:
  - /etc/openvpn:/etc/openvpn:rw
  - /run/openvpn:/run/openvpn:ro
```

This gives the backend container:
- Read/write access to easy-rsa PKI (for cert generation/revocation)
- Read/write access to server.conf and CCD directory
- Read-only access to the management socket

### Management Interface

The management interface is configured in server.conf as:

```
management /run/openvpn/management.sock unix
```

Python modules (`status_reader.py`, `enforcement.py`) connect to this
socket using `socket.AF_UNIX` to:
- Query live client status (`status 2` command)
- Kill active sessions (`kill <CN>` command)

## Modules

### `setup_server.sh`

One-time server bootstrap. Run on the host as root:

```bash
sudo ./setup_server.sh eth0 1194 udp
```

Installs OpenVPN + easy-rsa, generates CA/server certs, creates
`server.conf`, enables IP forwarding, sets up NAT, and starts the
systemd service.

### `config_writer.py`

Renders the `ServerConfig` DB row into a valid `server.conf` file.
Called by the backend when a sudo admin edits server settings.

```python
from vpn_core.config_writer import ServerConfigRow, apply_server_config

cfg = ServerConfigRow(port=1194, protocol="udp", dns_servers=["1.1.1.1"])
apply_server_config(cfg)
```

### `client_manager.py`

Certificate lifecycle operations:

```python
from vpn_core.client_manager import create_client, revoke_client, list_clients

# Create a new client
ovpn = create_client("alice", public_ip="1.2.3.4")

# Revoke
revoke_client("alice")

# List all clients
clients = list_clients()
```

### `status_reader.py`

Reads live client status from the management interface:

```python
from vpn_core.status_reader import get_live_status

clients = get_live_status()
for c in clients:
    print(f"{c.common_name}: {c.bytes_received} bytes in, {c.bytes_sent} bytes out")
```

### `enforcement.py`

Session management without full revocation:

```python
from vpn_core.enforcement import kill_client_session, disable_client, enable_client

# Kill a session (client can reconnect)
kill_client_session("alice")

# Disable via CCD (client cannot reconnect)
disable_client("alice")

# Re-enable
enable_client("alice")
```

## Hook Scripts

### `hooks/client-connect.sh`

Called on each client connection. Checks:
1. Is the client disabled via CCD?
2. Is the client expired?
3. Is the client within their allowed hours?

Exits non-zero to refuse the connection.

### `hooks/client-disconnect.sh`

Called on each client disconnect. Logs the event and updates the
state file with byte counters and last-seen timestamp.

## State Files

Runtime per-client state is stored in `/etc/openvpn/server/state/`:

```json
{
  "expire_at": "2025-12-31T23:59:59",
  "allowed_hours": [["08:00", "12:00"], ["18:00", "22:00"]],
  "last_disconnect": "2025-01-15T14:30:00",
  "last_bytes_received": 1234567,
  "last_bytes_sent": 9876543
}
```

The backend writes these files when creating/updating users. The connect
hook reads them for access control decisions.

# Manual Testing: vpn-core

This document describes how to manually verify the vpn-core modules
on a real Linux host.  These tests require root access and a working
OpenVPN installation.

## Prerequisites

- A clean Ubuntu 22.04+ or Debian 12+ VM (or a fresh VPS)
- Root access
- Network interface with a public or routable IP
- Python 3.10+ installed on the host

## 1. Test setup_server.sh

### 1.1 Clean install

```bash
# Identify your network interface
ip -4 addr | grep inet | grep -v 127.0.0.1

# Run the setup script (replace eth0 with your interface)
sudo ./vpn-core/setup_server.sh eth0 1194 udp
```

**Expected output:**
- Packages installed (openvpn, openssl, ca-certificates, iptables)
- easy-rsa downloaded and PKI initialised
- CA, server, and DH certificates generated
- server.conf created at /etc/openvpn/server/server.conf
- IP forwarding enabled
- NAT/iptables rule added
- OpenVPN systemd service started and enabled

### 1.2 Verify installation

```bash
# Check OpenVPN is running
systemctl status openvpn-server@server

# Check server.conf exists and has content
cat /etc/openvpn/server/server.conf

# Check certificates exist
ls -la /etc/openvpn/server/*.crt /etc/openvpn/server/*.key

# Check management socket exists
ls -la /run/openvpn/management.sock

# Check CCD directory exists
ls -la /etc/openvpn/server/ccd

# Check hooks are installed
ls -la /etc/openvpn/server/hooks/

# Check iptables rule
iptables -t nat -L POSTROUTING | grep 10.8.0.0
```

### 1.3 Idempotency test

```bash
# Run setup again — should skip and say "already configured"
sudo ./vpn-core/setup_server.sh eth0 1194 udp
```

**Expected:** Script detects existing server.conf and exits early.

---

## 2. Test client_manager.py

### 2.1 Create a client

```bash
cd /home/ali/Desktop/easy-openVPN
pip install -e vpn-core/

python3 -c "
from vpn_core.client_manager import create_client
ovpn = create_client('testuser', public_ip='YOUR_SERVER_IP')
with open('/tmp/testuser.ovpn', 'w') as f:
    f.write(ovpn)
print('Client created successfully')
"
```

**Expected:** `/tmp/testuser.ovpn` contains a valid .ovpn profile with
inline CA cert, client cert, client key, and TLS crypt key.

### 2.2 Import the .ovpn file

Copy the .ovpn file to your local machine and import it into an OpenVPN
client (e.g., OpenVPN Connect, NetworkManager).

**Expected:** Client connects successfully, receives an IP in the
10.8.0.0/24 range.

### 2.3 List clients

```bash
python3 -c "
from vpn_core.client_manager import list_clients
clients = list_clients()
for c in clients:
    print(f'{c.common_name}: {c.status} (expires {c.expiry_date})')
"
```

**Expected:** Lists all clients from the easy-rsa index.txt.

### 2.4 Revoke a client

```bash
python3 -c "
from vpn_core.client_manager import revoke_client
revoke_client('testuser')
print('Client revoked')
"
```

**Expected:**
- Certificate revoked in easy-rsa
- CRL updated and copied to /etc/openvpn/server/crl.pem
- .req and .key files removed from easy-rsa PKI

After revocation, the OpenVPN client should be unable to reconnect.

---

## 3. Test status_reader.py

### 3.1 Connect a client first

Connect a client using the .ovpn file created in step 2.

### 3.2 Read live status

```bash
python3 -c "
from vpn_core.status_reader import get_live_status
clients = get_live_status()
for c in clients:
    print(f'{c.common_name} from {c.real_address}: '
          f'rx={c.bytes_received} tx={c.bytes_sent}')
"
```

**Expected:** Lists connected clients with byte counters.

### 3.3 Test with no clients connected

Disconnect the client and run the same command.

**Expected:** Returns an empty list (no error).

### 3.4 Test with management socket unreachable

```bash
# Temporarily move the socket
sudo mv /run/openvpn/management.sock /run/openvpn/management.sock.bak

python3 -c "
from vpn_core.status_reader import get_live_status
result = get_live_status()
print(f'Result: {result}')
"

# Restore the socket
sudo mv /run/openvpn/management.sock.bak /run/openvpn/management.sock
```

**Expected:** Returns empty list, logs a warning, does not crash.

---

## 4. Test enforcement.py

### 4.1 Kill a client session

With a client connected:

```bash
python3 -c "
from vpn_core.enforcement import kill_client_session
result = kill_client_session('testuser')
print(f'Kill result: {result}')
"
```

**Expected:**
- Client is disconnected
- Returns True
- Client can reconnect (certificate is still valid)

### 4.2 Disable a client

```bash
python3 -c "
from vpn_core.enforcement import disable_client
result = disable_client('testuser')
print(f'Disable result: {result}')
"
```

**Expected:**
- CCD file created at /etc/openvpn/server/ccd/testuser
- Active session killed
- Client cannot reconnect (rejected by hook)

### 4.3 Enable a client

```bash
python3 -c "
from vpn_core.enforcement import enable_client
result = enable_client('testuser')
print(f'Enable result: {result}')
"
```

**Expected:**
- CCD file removed
- Client can reconnect

### 4.4 Check if client is disabled

```bash
python3 -c "
from vpn_core.enforcement import is_client_disabled
print(f'Disabled: {is_client_disabled(\"testuser\")}')
"
```

---

## 5. Test config_writer.py

### 5.1 Render a server.conf

```bash
python3 -c "
from vpn_core.config_writer import ServerConfigRow, render_server_conf

cfg = ServerConfigRow(
    port=1194,
    protocol='udp',
    public_ip='YOUR_SERVER_IP',
    dns_servers=['1.1.1.1', '1.0.0.1'],
    cipher='AES-256-GCM',
    auth='SHA256',
)
print(render_server_conf(cfg))
"
```

**Expected:** Prints a valid OpenVPN server.conf with all directives.

### 5.2 Apply config (optional — restarts OpenVPN)

```bash
python3 -c "
from vpn_core.config_writer import ServerConfigRow, apply_server_config

cfg = ServerConfigRow(port=1194, protocol='udp')
result = apply_server_config(cfg)
print(f'Applied: {result}')
"
```

**Expected:**
- server.conf written (backup of old one created)
- OpenVPN service restarted
- Returns True

---

## 6. Test hook scripts

### 6.1 Test client-connect hook manually

```bash
# Set environment variables and run the hook
common_name="testuser" \
trusted_ip="192.168.1.100" \
ifconfig_pool_remote_ip="10.8.0.5" \
script_type="client-connect" \
sudo bash /etc/openvpn/server/hooks/client-connect.sh

echo "Exit code: $?"
cat /var/log/openvpn-hooks.log | tail -5
```

**Expected:** Exit code 0, log entry showing client allowed.

### 6.2 Test with expired client

```bash
# Create a state file with expired timestamp
echo '{"expire_at": "2020-01-01T00:00:00"}' | \
    sudo tee /etc/openvpn/server/state/testuser.json

common_name="testuser" \
trusted_ip="192.168.1.100" \
ifconfig_pool_remote_ip="10.8.0.5" \
script_type="client-connect" \
sudo bash /etc/openvpn/server/hooks/client-connect.sh

echo "Exit code: $?"
```

**Expected:** Exit code 1 (connection refused), log shows "expired".

### 6.3 Test with disabled CCD file

```bash
# Create CCD disable file
echo "disable" | sudo tee /etc/openvpn/server/ccd/testuser

common_name="testuser" \
trusted_ip="192.168.1.100" \
ifconfig_pool_remote_ip="10.8.0.5" \
script_type="client-connect" \
sudo bash /etc/openvpn/server/hooks/client-connect.sh

echo "Exit code: $?"

# Clean up
sudo rm /etc/openvpn/server/ccd/testuser
```

**Expected:** Exit code 1 (connection refused), log shows "disabled".

---

## 7. End-to-end test

### 7.1 Full flow

1. Run `setup_server.sh` on a fresh host
2. Create a client via Python
3. Connect with the .ovpn file
4. Verify connection with `get_live_status()`
5. Kill the session with `kill_client_session()`
6. Verify disconnection
7. Disable the client with `disable_client()`
8. Attempt to reconnect — should fail
9. Enable the client with `enable_client()`
10. Reconnect — should succeed
11. Revoke the client with `revoke_client()`
12. Attempt to reconnect — should fail permanently

### 7.2 Verify permissions

```bash
# CRL should be readable by nobody
ls -la /etc/openvpn/server/crl.pem
# Should show: -rw-r----- nobody nogroup (or nobody nobody)

# CCD directory should be readable
ls -la /etc/openvpn/server/ccd/

# Hooks should be executable
ls -la /etc/openvpn/server/hooks/
```

---

## Troubleshooting

### OpenVPN won't start

```bash
# Check logs
journalctl -u openvpn-server@server -n 50

# Check config syntax
openvpn --config /etc/openvpn/server/server.conf --verb 4
```

### Management socket not found

```bash
# Check if OpenVPN created it
ls -la /run/openvpn/

# Check server.conf has management directive
grep management /etc/openvpn/server/server.conf
```

### easy-rsa command fails

```bash
# Check easy-rsa is installed
ls -la /etc/openvpn/easy-rsa/easyrsa

# Run manually
cd /etc/openvpn/easy-rsa
./easyrsa --version
```

### Hook script errors

```bash
# Check logs
cat /var/log/openvpn-hooks.log

# Run hook manually with debug
bash -x /etc/openvpn/server/hooks/client-connect.sh
```

# Installation Guide

This guide walks you through installing eovpanel on a fresh Ubuntu/Debian VPS using the CLI installer.

## Quick Start (One-Line Install)

Run this single command on your server as root:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Liwyd/easy-openVPN/main/installer/bootstrap.sh)"
```

This will:
1. Install Python 3.12+ if not present
2. Clone the repository to `/opt/eovpanel`
3. Set up a Python virtual environment
4. Launch the CLI installer

## Requirements

- **OS:** Ubuntu 20.04+ or Debian 11+
- **RAM:** 512MB minimum (1GB+ recommended)
- **Disk:** 2GB free space
- **Access:** Root privileges (sudo)
- **Network:** Public IP with port 1194 (UDP) available

## CLI Usage

```
eovpanel <command> [options]

Commands:
  install       Install eovpanel on this server
  configure     Modify an existing installation
  uninstall     Remove eovpanel and optionally all data
  status        Show current installation status
```

### Install

**Interactive mode** (prompts for each setting):
```bash
sudo eovpanel install
```

**Non-interactive mode** (uses defaults, no prompts):
```bash
sudo eovpanel install -y
```

**Custom settings:**
```bash
sudo eovpanel install --port 1194 --protocol udp --admin-user admin --admin-pass mypassword
```

**With Telegram:**
```bash
sudo eovpanel install --telegram-token "123456:ABC-DEF" --telegram-chat "123456789"
```

**With TLS (domain):**
```bash
sudo eovpanel install --domain panel.example.com --email admin@example.com
```

### Configure

```bash
# Rotate JWT secret
eovpanel configure --rotate-jwt

# Set up TLS
eovpanel configure --domain panel.example.com --email admin@example.com

# Enable Telegram
eovpanel configure --enable-telegram --telegram-token "123456:ABC-DEF" --telegram-chat "123456789"

# Disable Telegram
eovpanel configure --disable-telegram
```

### Uninstall

```bash
# Stop containers only (safest)
sudo eovpanel uninstall --stop

# Remove containers (keep OpenVPN data)
sudo eovpanel uninstall --remove

# Full purge (wipe everything — irreversible!)
sudo eovpanel uninstall --purge
```

### Status

```bash
eovpanel status
```

## Installer Walkthrough

### Step 1: System Check

```
[1/5] System check
  [*] OS: ubuntu 22.04
  [*] Root: yes
  [+] No existing OpenVPN found. Will install from scratch.
```

The installer automatically detects your OS and checks for root privileges. If an existing OpenVPN installation is found, you'll be asked whether to reuse it.

---

### Step 2: VPN Settings

```
[2/5] VPN settings
  [*] Port: 1194
  [*] Protocol: udp
  [*] Public IP: 203.0.113.42
  [*] Interface: eth0
```

Default settings work for most setups. The public IP is auto-detected.

---

### Step 3: Admin Account

```
[3/5] Admin account
  Admin username [admin]: 
  Admin password: ********
  [+] Admin credentials ready.
```

Create the first sudo administrator for the web panel. Change the password after first login!

---

### Step 4: Telegram (Optional)

```
[4/5] Telegram (optional)
  Enable Telegram bot notifications now? [y/N]: n
  [*] Telegram skipped. You can enable it later from the panel Settings.
```

Press N to skip. You can enable Telegram later from the web panel.

---

### Step 5: Domain & TLS (Optional)

```
[5/5] Domain & TLS
  Set up a domain with free TLS certificate (via ESSL)? [y/N]: n
  [*] TLS skipped. Panel will run over plain HTTP.
```

Press N to skip. The panel works perfectly over plain HTTP.

---

### Installation Progress

```
Running installation
─────────────────────
  [*] Installing system packages...
  [+] System packages installed.
  [*] Setting up OpenVPN server...
  [+] OpenVPN server configured.
  [*] Configuring backend environment...
  [+] Backend .env written to /opt/eovpanel/backend/.env
  [*] Seeding admin account (admin)...
  [+] Admin account seeded.
  [*] Building and starting containers...
  [+] Containers started successfully.
```

Each step streams live output from the underlying commands.

---

### Installation Complete

```
Installation complete!
──────────────────────

  Panel URL:     http://203.0.113.42
  Login:         admin / <password>
  OpenVPN CA:    /opt/eovpanel/vpn-core/
  Backend .env:  /opt/eovpanel/backend/.env
  Docker Compose: /opt/eovpanel/docker/docker-compose.yml

  Next steps:
    1. Open the panel URL in your browser
    2. Log in with your admin credentials
    3. Change the default admin password immediately!
    4. Create your first VPN user from the Users page
    5. Download the .ovpn config and test connectivity

  To reconfigure, run: eovpanel configure
  To uninstall, run:   eovpanel uninstall
```

---

## Idempotency

Running `eovpanel install` on an already-installed system will detect the existing installation and ask whether to overwrite the config.

## Rollback on Failure

If an installation step fails, the installer shows the error and exits. Partial state is preserved for manual inspection.

## File Locations

| Path | Description |
|------|-------------|
| `/opt/eovpanel/` | Repository root |
| `/opt/eovpanel/backend/.env` | Backend configuration |
| `/opt/eovpanel/docker/docker-compose.yml` | Container definitions |
| `/etc/openvpn/server/` | OpenVPN config, certs, keys |
| `/etc/openvpn/server/easy-rsa/` | easy-rsa PKI directory |
| `/opt/eovpanel/.venv-installer/` | Python venv for the installer |

## Troubleshooting

### Installer won't start
- Ensure you're running as root: `sudo bash -c "$(curl -fsSL ...)"`
- Check Python version: `python3 --version` (needs 3.12+)

### Containers won't start
- Check Docker: `docker ps`
- Check logs: `docker logs eovpanel-backend`
- Check .env: `cat /opt/eovpanel/backend/.env`

### Can't connect to panel
- Check port 80: `curl -I http://YOUR_IP`
- Check nginx: `docker logs eovpanel-frontend`
- Check firewall: `ufw allow 80/tcp`

### OpenVPN not working
- Check service: `systemctl status openvpn-server@server`
- Check config: `cat /etc/openvpn/server/server.conf`
- Check logs: `journalctl -u openvpn-server@server`

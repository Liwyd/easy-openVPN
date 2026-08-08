# Installation Guide

This guide walks you through installing eovpanel on a fresh Ubuntu/Debian VPS using the TUI installer.

## Quick Start (One-Line Install)

Run this single command on your server as root:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Liwyd/easy-openVPN/main/installer/bootstrap.sh)"
```

This will:
1. Install Python 3.12+ if not present
2. Clone the repository to `/opt/eovpanel`
3. Set up a Python virtual environment
4. Launch the TUI installer

## Requirements

- **OS:** Ubuntu 20.04+ or Debian 11+
- **RAM:** 512MB minimum (1GB+ recommended)
- **Disk:** 2GB free space
- **Access:** Root privileges (sudo)
- **Network:** Public IP with port 1194 (UDP) available

## Installer Walkthrough

### Screen 1: Welcome Menu

```
  ______              ______          _ _
 |  ____|            |  ____|        | (_)
 | |___   _ __  ___  | |__   _ __ ___| |_ ___  _ __ _   _
 |  __| | '__/ _ \ |  __| | '__/ _ \ __/ _ \| '__| | | |
 | |    | | |  __/ | |    | | |  __/ || (_) | |  | |_| |
 |_|    |_|  \___| |_|    |_|  \___|\__\___/|_|   \__, |
                                                     __/ |
                                                    |___/

eovpanel Installer
OpenVPN Management Panel

  Install
  Configure
  Uninstall
  Exit
```

Use **arrow keys** to navigate and **Enter** to select. Choose:
- **Install** — Fresh installation on a new server
- **Configure** — Modify settings of an existing installation
- **Uninstall** — Remove eovpanel from this server
- **Exit** — Quit the installer

---

### Screen 2: System Check (Install Flow)

The installer automatically detects your OS and checks for root privileges:

```
=== System Check ===
OS: ubuntu 22.04
Root: yes
Debian-like: yes
No existing OpenVPN installation found.
Will install OpenVPN from scratch.
```

If an existing OpenVPN installation is detected, you'll be asked whether to reuse it or abort.

---

### Screen 3: VPN Settings

```
=== VPN Settings ===
Detected public IP: 203.0.113.42
Detected interface: eth0

Default settings:
  Port:     1194
  Protocol: UDP
  Public IP: 203.0.113.42
  Interface: eth0

Press [Continue] to accept defaults, or go back to modify.
```

Default settings work for most setups. Press **Continue** to proceed.

---

### Screen 4: Admin Account

```
=== Admin Account ===

Create the first sudo administrator for the web panel.
Default credentials (press [Continue] to accept):
  Username: admin
  Password: admin

⚠ Change the password after first login!
```

Press **Continue** to create the admin with default credentials, then change it after login.

---

### Screen 5: Telegram Bot (Optional)

```
=== Telegram Bot (Optional) ===

Telegram bot integration sends notifications when:
  - A new client connects/disconnects
  - A user's quota is used up
  - A user's subscription expires

You can configure this later from the panel's Settings page.

Press [Continue] to skip Telegram setup.
```

Press **Skip** to continue without Telegram. You can enable it later from the web panel.

---

### Screen 6: Domain & TLS (Optional)

```
=== Domain & TLS (Optional) ===

You can optionally set up a domain name with a free TLS
certificate so the panel is accessible over HTTPS.

Requirements:
  - A domain name pointed at this server's IP
  - Port 80 open (for ACME HTTP-01 challenge)

The panel works fine over plain HTTP without TLS.
You can add TLS later from the Configure menu.

Press [Skip] to continue without TLS.
```

Press **Skip** to continue over plain HTTP. The panel works perfectly without TLS.

---

### Screen 7: Installation Progress

```
=== Running Installation ===

--- Step 1/5: Install system packages ---
Updating package lists...
Installing required packages...
System packages installed.

--- Step 2/5: Set up OpenVPN server ---
Running setup_server.sh eth0 1194 udp
[*] Installing packages...
[*] Downloading easy-rsa 3.2.6...
[*] Initialising PKI...
OpenVPN server configured.

--- Step 3/5: Configure backend .env ---
Configuring backend environment...
Backend .env written to /opt/eovpanel/backend/.env

--- Step 4/5: Seed admin account ---
Seeding initial admin account (admin/admin)...
Admin account seeded.

--- Step 5/5: Build and start containers ---
Building and starting containers...
Containers started successfully.
```

Each step streams live output from the underlying commands. If a step fails, you'll see the error and can choose to retry or abort.

---

### Screen 8: Installation Complete

```
╔══════════════════════════════════════════╗
║       Installation Complete!             ║
╚══════════════════════════════════════════╝

  Panel URL:     http://203.0.113.42
  Login:         admin / admin
  OpenVPN CA:    /opt/eovpanel/vpn-core/
  Backend .env:  /opt/eovpanel/backend/.env
  Docker Compose:/opt/eovpanel/docker/docker-compose.yml

Next steps:
  1. Open the panel URL in your browser
  2. Log in with admin / admin
  3. Change the default admin password immediately!
  4. Create your first VPN user from the Users page
  5. Download the .ovpn config and test connectivity

To reconfigure the panel, run the installer again and
select 'Configure' from the main menu.
```

---

## Configure Flow

Run the installer again and select **Configure** to:

- **Change panel domain / TLS** — Add or update TLS certificates via ESSL
- **Rotate JWT secret** — Generate a new JWT signing key
- **Edit OpenVPN settings** — Guide to editing via the web panel (same settings page as the TUI would use)

## Uninstall Flow

Select **Uninstall** from the main menu to choose what to remove:

| Option | What it does |
|--------|-------------|
| **Stop containers only** | Stops backend/frontend containers. All data preserved. |
| **Remove containers** | Stops + removes containers, networks, images. OpenVPN data preserved. |
| **Full purge** | Removes everything: containers, OpenVPN certs/keys, database. **Irreversible.** |

The default (safest) option is **Stop containers only**.

## Idempotency

Running **Install** on an already-installed system will detect the existing installation and offer to jump into **Configure** instead of duplicating work.

## Rollback on Failure

If an installation step fails midway, the installer shows the error and offers:
- **Retry** — Attempt the failed step again
- **Abort** — Stop installation, leaving partial state in place for manual inspection

Partial state is preserved by default since it's more useful for debugging than a clean slate.

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

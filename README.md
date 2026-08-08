<p align="center">
  <img src="docs/logo.svg" width="120" alt="eovpanel logo" />
</p>

<h1 align="center">eovpanel</h1>

<p align="center">
  A lightweight, single-node OpenVPN management panel with hierarchical admins,
  per-user quotas, subscription links, and a Telegram logging bot.
</p>

<p align="center">
  <a href="https://github.com/Liwyd/easy-openVPN/actions"><img src="https://github.com/Liwyd/easy-openVPN/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Liwyd/easy-openVPN" alt="License" /></a>
  <a href="https://github.com/Liwyd/easy-openVPN/stargazers"><img src="https://img.shields.io/github/stars/Liwyd/easy-openVPN" alt="Stars" /></a>
</p>

---

## What is this?

eovpanel is a web-based management panel for OpenVPN servers.  It wraps [Nyr's openvpn-install](https://github.com/Nyr/openvpn-install) script with a FastAPI backend, a React dashboard, and a one-command TUI installer — giving you user management, traffic accounting, time-based access control, and subscription download links, all without leaving your terminal or browser.

**Designed for:** VPS providers reselling VPN access, small teams sharing a single OpenVPN server, personal use on a single VPS.

## Features

| Feature | Description |
|---------|-------------|
| **Hierarchical admins** | Super admin creates sub-admins, each with their own user quota (bandwidth + user slots).  Designed for reseller workflows. |
| **Per-user traffic limits** | Set byte quotas per user.  Traffic is polled from the OpenVPN management socket every 30 seconds. |
| **Time-based access** | Expiry dates + allowed-hour access windows (e.g., 9am–5pm only).  Enforced by OpenVPN connect/disconnect hooks. |
| **Subscription links** | Each user gets a unique, random URL to download their `.ovpn` file — no login required on the client side. |
| **In-panel server config** | Change protocol, port, cipher, DNS, MTU from the Settings page.  Config is rendered to `server.conf` and OpenVPN is reloaded. |
| **Telegram notifications** | Optional bot logs user connects/disconnects, quota exhaustion, and admin actions to a Telegram chat. |
| **TUI installer** | One command installs everything: system packages, OpenVPN, backend, frontend, Docker containers.  Works on fresh Ubuntu/Debian. |
| **Docker deployment** | Backend + frontend run in Docker Compose.  OpenVPN runs on the host (mounted into the container).  SQLite by default, PostgreSQL optional. |
| **TLS via ESSL** | Optional HTTPS certificates from [erfjab/ESSL](https://github.com/erfjab/ESSL), provisioned through the TUI installer. |
| **Chakra UI dashboard** | Red/black theme with light/dark mode.  Traffic charts, quota usage bars, status badges, user/admin tables with inline actions. |
| **Security hardening** | Login rate limiting (5 attempts/min/IP), username validation, CSP headers, threaded job guards, admin isolation. |

## Screenshots

> **Note:** Screenshots are placeholders.  Contributions of real screenshots are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

### Dashboard
<!-- Replace with actual screenshot: doc/images/dashboard.png -->
Stat cards (total users, traffic), quota usage bar, 30-day traffic chart, user status breakdown, top users table.  Red accent on dark background.

### User Management
<!-- Replace with actual screenshot: doc/images/users.png -->
Searchable user table with status badges (active/limited/expired/disabled), data usage progress bars, expiry dates, time windows.  Inline actions: edit, enable/disable, download .ovpn, copy/regenerate subscription link, reset usage, delete.

### Admin Management
<!-- Replace with actual screenshot: doc/images/admins.png -->
Admin table with sudo/sub-admin role badges, data quota bars, inline disable toggle.  Only visible to sudo admins.

### Login
<!-- Replace with actual screenshot: doc/images/login.png -->
Centered card with red accent border, username/password fields, error feedback.

## Quick Install

Run this on a fresh Ubuntu/Debian VPS as root:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Liwyd/easy-openVPN/main/installer/bootstrap.sh)"
```

The TUI installer will walk you through:
1. System check (OS, root, existing OpenVPN)
2. VPN settings (port, protocol, interface — defaults work for most setups)
3. Admin account (default: `admin` / `admin` — change after first login)
4. Telegram bot (optional, skippable)
5. Domain & TLS (optional, skippable via [ESSL](https://github.com/erfjab/ESSL))
6. Docker build & launch

After install, open `http://YOUR_SERVER_IP` in your browser.

## Docker Deploy (Manual)

If you prefer to skip the TUI installer:

```bash
git clone https://github.com/Liwyd/easy-openVPN.git && cd easy-openVPN
cp .env.example .env    # edit with your settings — set JWT_SECRET_KEY!
cd docker && docker compose up -d --build
```

Backend runs on port 8000, frontend nginx on port 80.  OpenVPN must be installed on the host separately.

See [docs/docker-verification.md](docs/docker-verification.md) for the full verification checklist.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (sync), Alembic, Pydantic v2 |
| Frontend | React 19, TypeScript, Vite, Chakra UI v3 |
| VPN Engine | OpenVPN + easy-rsa (via Nyr's script logic) |
| Installer | Python, Textual TUI |
| Scheduling | APScheduler (in-process, no Redis) |
| Auth | JWT (access + refresh tokens) |
| Database | SQLite (default), PostgreSQL (supported) |
| Deployment | Docker Compose; OpenVPN on host |

## Project Structure

```
backend/        FastAPI API server + Alembic migrations
frontend/       React + TypeScript + Vite + Chakra UI
installer/      Textual TUI installer / configurator / uninstaller
vpn-core/       OpenVPN helpers (wraps easy-rsa + Nyr's script logic)
docker/         Dockerfiles and docker-compose files
docs/           Architecture docs, ADRs, and verification guides
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/eovpanel.db` | Database connection string |
| `JWT_SECRET_KEY` | `changeme-in-production` | JWT signing key — **change this!** |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `SUDO_USERNAME` | `admin` | Initial super admin username (first run only) |
| `SUDO_PASSWORD` | `admin` | Initial super admin password (first run only) |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed CORS origins |
| `TELEGRAM_ENABLED` | `false` | Enable Telegram notification bot |
| `TELEGRAM_BOT_TOKEN` | | Bot token from @BotFather |
| `TELEGRAM_ADMIN_CHAT_IDS` | | Comma-separated chat IDs for notifications |
| `OPENVPN_MANAGEMENT_SOCKET` | `/run/openvpn/management.sock` | OpenVPN mgmt socket path |
| `OPENVPN_STATUS_LOG` | `/etc/openvpn/status.log` | OpenVPN status log path |
| `EASYRSA_DIR` | `/etc/openvpn/easy-rsa` | easy-rsa PKI directory |

See [`.env.example`](.env.example) for the full annotated list.

## Why not just use Marzban?

[Marzban](https://github.com/gozargah/marzban) is excellent and was the direct inspiration for eovpanel's UX.  The differences are deliberate:

- **OpenVPN-focused.**  Marzban is built on Xray-core and supports VLESS/Trojan/Shadowsocks.  eovpanel is built on OpenVPN — if you need OpenVPN specifically (for client compatibility, corporate firewall traversal, or because you already run it), this is purpose-built for that.
- **Lighter.**  No Xray, no Redis, no Celery.  SQLite by default, APScheduler in-process, sync SQLAlchemy.  Fewer moving parts to break on a $5 VPS.
- **Single-node.**  Marzban supports multi-node clustering and distributed user management.  eovpanel is designed for a single server with one OpenVPN instance.  This is a constraint, not a roadmap item.
- **Hierarchical admins.**  eovpanel's admin quota model (super admin → sub-admin → users) is designed for reseller workflows where you need per-reseller bandwidth tracking.
- **TUI installer.**  One command from SSH to a running panel.  Marzban has Docker Compose instructions; eovpanel has a guided terminal wizard.

## Documentation

- **[Architecture](docs/architecture.md)** — ADRs explaining every major design decision
- **[Installation](docs/installation.md)** — Full TUI installer walkthrough with screenshots
- **[Docker Verification](docs/docker-verification.md)** — Step-by-step verification checklist
- **[VPN Core Testing](docs/manual-testing-vpn-core.md)** — Manual test guide for the OpenVPN integration layer

## Credits

- [Marzban](https://github.com/gozargah/marzban) — UX inspiration and architectural patterns
- [Nyr's openvpn-install](https://github.com/Nyr/openvpn-install) — OpenVPN installation and configuration logic ([MIT license](https://github.com/Nyr/openvpn-install/blob/master/LICENSE))
- [erfjab/ESSL](https://github.com/erfjab/ESSL) — TLS certificate acquisition for HTTPS

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, test instructions, and PR guidelines.

## License

[MIT](LICENSE) — Copyright (c) 2026 eovpanel contributors.

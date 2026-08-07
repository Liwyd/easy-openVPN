# eovpanel

An easy-to-use OpenVPN management panel for commercial and personal usage.

Inspired by [Marzban](https://github.com/gozargah/marzban)'s UX, but built on
top of [Nyr's openvpn-install](https://github.com/Nyr/openvpn-install) script
instead of Xray-core.

## Features

- **User Management** — create, edit, and delete VPN users with per-user quotas
- **Traffic Accounting** — real-time bandwidth monitoring via OpenVPN management interface
- **Time-Based Limits** — per-user expiry dates and allowed-hour access windows
- **Subscription Links** — unique `.ovpn` download URLs per user
- **Admin Hierarchy** — super admin → admin → user quota model for resellers
- **Telegram Notifications** — optional bot for alerts and logging
- **TUI Installer** — terminal-based setup wizard for fresh Ubuntu/Debian servers
- **Dockerized** — backend (FastAPI) and frontend (React) run in Docker; OpenVPN runs on the host
- **Light/Dark Theme** — Chakra UI with red accent palette

## Tech Stack

| Layer        | Technology                                      |
|--------------|------------------------------------------------|
| Backend      | Python 3.12, FastAPI, SQLAlchemy 2.0 (sync), Alembic, Pydantic v2 |
| Frontend     | React, TypeScript, Vite, Chakra UI             |
| VPN Engine   | OpenVPN + easy-rsa (via Nyr's script logic)    |
| Installer    | Python, Textual TUI                            |
| Scheduling   | APScheduler (in-process, no Redis needed)      |
| Auth         | JWT (access + refresh tokens)                  |
| Database     | SQLite (default), PostgreSQL (supported)       |
| Deployment   | Docker Compose (backend + frontend); OpenVPN on host |

## Project Structure

```
backend/        FastAPI API server (app/ subfolder)
frontend/       React + TypeScript + Vite + Chakra UI
installer/      Textual TUI installer
vpn-core/       OpenVPN helpers (wraps easy-rsa + Nyr's script logic)
docker/         Dockerfiles and docker-compose.yml
docs/           Architecture docs and ADRs
```

## Quick Start

```bash
# Backend
cd backend && cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Credits

- [Marzban](https://github.com/gozargah/marzban) — UX inspiration and architectural patterns
- [Nyr's openvpn-install](https://github.com/Nyr/openvpn-install) — OpenVPN installation and configuration logic (MIT license)
- [ESSL](https://github.com/erfjab/ESSL) — TLS certificate acquisition (future integration)

## License

MIT — see [LICENSE](LICENSE) for details.

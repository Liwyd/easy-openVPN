# Changelog

All notable changes to eovpanel will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Installer TUI crashed on launch with `AttributeError: 'InstallerApp' object has no attribute 'register_screen'`. Replaced `register_screen()` calls with `SCREENS` class dict for compatibility with all Textual versions.

## [0.1.0] — 2026-08-08

Initial public release.  Everything below covers stages 0 through 11.

### Added

- **OpenVPN core wrapper** — Python bindings around easy-rsa for client creation,
  revocation, listing, and status reading.  Based on Nyr's openvpn-install script
  logic.  Management socket interface for live client status and kill commands.

- **Database models** — SQLAlchemy models for admins, users, server config, traffic
  logs, and subscription tokens.  Hierarchical admin-to-user ownership.  Alembic
  migrations for SQLite and PostgreSQL.

- **Admin authentication & hierarchy** — JWT-based auth (access + refresh tokens).
  Super admin (sudo) creates sub-admins.  Each admin owns a quota slice (bandwidth
  + user slots) and can only manage their own users.

- **Telegram notification bot** — Optional bot that logs user connects, disconnects,
  quota exhaustion, and admin actions to a Telegram chat.  Configurable via
  environment variables.

- **User management API** — CRUD endpoints for users with per-user traffic limits,
  expiry dates, allowed-hour access windows, and subscription token generation.
  Subscription endpoint (`/sub/{token}`) serves `.ovpn` files without authentication.

- **Traffic accounting** — Background job polls the OpenVPN management socket every
  30 seconds, records per-client byte counters, and computes cumulative usage.

- **Quota enforcement** — Background jobs check user expiry, traffic limits, and
  allowed-hour windows.  Disabled users are disconnected via the management socket.
  Periodic traffic counters are reset on a configurable schedule.

- **Frontend dashboard** — React SPA with Chakra UI v3.  Stat cards (total users,
  traffic), quota usage bar with percentage, 30-day traffic area chart (Recharts),
  user status breakdown, top users table.  Light/dark theme toggle.

- **User management page** — Searchable, paginated user table with status badges,
  data usage progress bars, expiry dates, time windows.  Inline actions: create,
  edit, enable/disable, download .ovpn, copy/regenerate subscription link, reset
  usage, delete.  Status filter dropdown.

- **Admin management page** — Paginated admin table with sudo/sub-admin role badges,
  data quota bars, inline disable toggle.  Create, edit, reset password, delete.
  Only visible to sudo admins.  Route-guarded in the frontend.

- **Settings page** — OpenVPN server configuration editor (protocol, port, cipher,
  DNS, MTU).  Saves to the database and triggers OpenVPN reload.

- **TUI installer** — Textual-based terminal UI for fresh Ubuntu/Debian servers.
  Walks through system check, VPN settings, admin account, Telegram bot, domain/TLS,
  and Docker deployment.  Supports install, configure, and uninstall flows.
  Idempotent — detects existing installations.  One-command bootstrap script.

- **Docker deployment** — Backend (FastAPI + Alembic + APScheduler) and frontend
  (React SPA + nginx) run in Docker Compose.  OpenVPN runs on the host with
  volumes mounted into the backend.  SQLite by default, PostgreSQL via overlay
  compose file.  Health checks on both services.

- **Security hardening** — Login rate limiting (5 failed attempts/min/IP, returns
  429 with Retry-After header).  Username validation (regex `[a-zA-Z0-9_-]{1,64}`,
  enforced at the Pydantic schema level).  CSP, Referrer-Policy, and
  Permissions-Policy headers on nginx.  `subscription_token` removed from admin
  API responses.  `threading.Lock` guards on all three background jobs to prevent
  concurrent execution overlap.

- **Test suite** — 170+ tests covering authentication, user CRUD, admin isolation,
  subscription endpoint security, rate limiting, username validation, input
  validation, password leak prevention, job lock behavior, bot formatting, and
  VPN-core logic.

### Known Limitations

- Single-node only — no clustering, replication, or distributed locking.
- In-memory rate limiters — reset on process restart.
- SQLite default — switch to PostgreSQL for higher concurrency.
- No WebSocket / real-time updates — dashboard polls via React Query.
- Single OpenVPN management socket — only one server instance managed.
- No automated cert renewal — manual revocation and recreation required.
- Telegram bot is notification-only — no interactive commands.

[0.1.0]: https://github.com/Liwyd/easy-openVPN/releases/tag/v0.1.0

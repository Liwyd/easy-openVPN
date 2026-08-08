# Architecture Decision Records

## ADR-001: Technology Stack & Deployment Model

### Status

Accepted

### Context

eovpanel is a single-node OpenVPN management panel inspired by [Marzban](https://github.com/gozargah/marzban), but built on top of [Nyr's openvpn-install](https://github.com/Nyr/openvpn-install) script instead of Xray-core. This ADR documents the foundational architectural decisions for stage 0.

### Decisions

#### FastAPI + Synchronous SQLAlchemy (not async)

We use synchronous SQLAlchemy (`Session`, not `AsyncSession`) with FastAPI. Justification:

- Matches Marzban's proven approach — the same patterns, dependency injection style, and `GetDB` context manager work identically.
- The bottleneck in this system is VPN I/O (management interface socket reads, byte counter parsing), not database queries. Async DB would add complexity (event loop management, `AsyncSession` lifecycle) with no measurable performance gain.
- Synchronous sessions are simpler to reason about, test, and debug. Alembic migrations and SQLAlchemy model definitions remain unchanged regardless of sync/async.
- The `get_db()` dependency + `GetDB` context manager provides clean session lifecycle management without async overhead.

#### APScheduler over Celery

We use APScheduler for background jobs (traffic accounting polling, user expiry checks) instead of Celery. Justification:

- APScheduler is a single-process, in-process scheduler — no Redis, RabbitMQ, or separate worker processes required. This aligns with our single-node constraint.
- Job definitions are plain Python functions with `@scheduled_job` decorators; auto-discovery via the `app/jobs/` package is trivial.
- For a single-node deployment managing hundreds (not millions) of VPN users, APScheduler's throughput is more than sufficient. If scaling needs arise, the job functions can be extracted to Celery workers later with minimal refactoring since they are already decoupled in `app/jobs/`.

#### Hierarchical Admin Quota Model

Unlike Marzban's flat admin model (each admin manages all users independently), eovpanel implements hierarchical resource quotas:

- **Super Admin** → owns the server, sets global limits (total bandwidth, max users, etc.)
- **Admin** → receives a quota slice from the super admin (e.g., 100 GB bandwidth, 50 user slots)
- **User** → receives a sub-quota from their admin (e.g., 10 GB bandwidth, 1 user slot)

Quota propagation rules:

- An admin cannot allocate more resources than they have available.
- Allocation is validated at creation time — if an admin tries to create a user with 20 GB quota but only has 15 GB remaining, the request is rejected with a clear error.
- Quota is enforced at the OpenVPN level via traffic accounting and time-based limits (see below).

This model is designed for reseller/multi-tenant scenarios where operators resell VPN access and need per-reseller usage tracking.

#### OpenVPN Traffic Accounting

Traffic accounting works by polling the OpenVPN management interface:

1. OpenVPN is started with `management <socket> unix` (or `management <port> localhost`) in `server.conf`.
2. A background job (APScheduler, every 30–60 seconds) connects to the management interface and issues the `status` command.
3. The `status` output contains per-client byte counters (`bytesin`/`bytesout` per Common Name).
4. These counters are written to a `TrafficLog` table in the database, with timestamps.
5. Cumulative usage is computed by summing byte deltas over the accounting period.
6. When a user's cumulative usage exceeds their quota, the admin is notified (and optionally the user is disconnected via the `kill` management command).

#### Time-Based Access Limits

Each user has two time-related fields:

- **`expire_at`** (datetime, nullable): Absolute expiry date/time. After this timestamp, the user's certificate is revoked or their connection is killed via the management interface.
- **`time_window_start`** / **`time_window_end`** (Time, nullable): A time-of-day window during which the user is allowed to connect (e.g., 08:00–12:00).  If both are set, the enforcement job checks the current time and kills sessions outside the window.  This is enforced by the `enforce_limits` background job, which disconnects users whose current time falls outside their allowed window.

Why this design: OpenVPN's script-based hooks (`client-connect`, `client-disconnect`) make runtime enforcement feasible. Unlike Xray's routing-based approach, OpenVPN can actively kill or reject connections based on custom logic in these scripts.

#### Subscription Link

Each user gets a long, random, unguessable subscription token:

- Generated at user creation time using `secrets.token_urlsafe(32)`.
- Stored as `subscription_token` in the `User` table.
- A public (no-auth) endpoint `GET /sub/{token}` returns the user's current `.ovpn` profile file.
- Users can bookmark this URL to always get their latest config (re-generated after password changes, server config changes, etc.).
- Token regeneration: the owning admin can regenerate the token, which invalidates the old link.  The subscription endpoint queries by token value, so a regenerated token means the old one simply doesn't match any user — no blacklist needed.
- This is similar to Marzban's subscription URL but returns a single OpenVPN profile instead of a multi-protocol config list.

#### Server Configuration Storage

OpenVPN server-wide settings (protocol, port, cipher, DNS servers, MTU, etc.) are stored in a single-row `ServerConfig` database table, not as a flat file. Justification:

- Database storage allows the panel's Settings page to read/write config atomically.
- Audit trail: config changes are timestamped and attributable to an admin.
- The `vpn-core` module is responsible for rendering the `ServerConfig` DB row into the actual `server.conf` file and triggering OpenVPN reload/restart when it changes.
- This separates "config as data" (DB) from "config as deployment artifact" (file system).

#### Backend-to-VPN-Core Communication: Direct Python Imports

The backend (FastAPI) and vpn-core (Python helpers wrapping easy-rsa + OpenVPN) run in the same process. They communicate via direct Python function calls, not IPC (no sockets, no HTTP, no message queues). Justification:

- Both components are Python packages in the same container.
- Avoids serialization overhead and failure modes of IPC.
- vpn-core functions are stateless helpers that operate on the file system (easy-rsa directory, OpenVPN config directory, management socket).
- The backend calls vpn-core functions synchronously (matching our sync SQLAlchemy approach).

#### Deployment: OpenVPN on Host, Backend/Frontend in Docker

OpenVPN itself runs directly on the HOST (not in a container), while the backend and frontend run in Docker containers. Justification:

- Nyr's openvpn-install script assumes host-level installation (systemd service, iptables rules, tun device). Containerizing OpenVPN requires `--net=host` and `--cap-add=NET_ADMIN`, which largely negates container isolation benefits.
- The backend needs access to:
  - The OpenVPN management interface socket (mounted as a Docker volume from `/etc/openvpn/`).
  - The easy-rsa directory (`/etc/openvpn/easy-rsa/`) for certificate management.
  - The OpenVPN status log for parsing.
- These are mounted as read-write volumes into the backend container.
- The frontend is a static build served by nginx inside its container, exposed on port 80/443.
- The TUI installer (`installer/`) runs directly on the host to set up both Docker containers and the host-level OpenVPN installation.

### Consequences

- Single-process architecture is simple to deploy and debug, but limits horizontal scaling (acceptable for single-node).
- Sync SQLAlchemy means all DB operations block the request thread, but VPN I/O is the real bottleneck.
- APScheduler jobs run in the same process — a crash restarts the scheduler but jobs may miss a beat (acceptable for traffic accounting granularity).
- OpenVPN on host means the installer must handle host-level package installation (iptables, openvpn, easy-rsa) outside of Docker.

### Known Limitations

These are deliberate scope boundaries, not bugs.  Contributors should understand them before proposing changes:

- **Single-node only.**  There is no clustering, replication, or distributed locking.  The backend, scheduler, and OpenVPN server all run on one machine.  Horizontal scaling would require a shared database, distributed job queue, and management-interface proxy — none of which are implemented.
- **In-memory rate limiters.**  Login and subscription rate limiters use in-memory sliding windows.  They reset on process restart and are not shared across multiple backend instances (relevant only if someone deploys multiple backend replicas behind a load balancer, which is not a supported topology).
- **SQLite as default database.**  The default `DATABASE_URL` uses SQLite, which is suitable for single-node with low concurrency.  For production with >50 concurrent admin operations, switch to PostgreSQL via `docker-compose.postgres.yml`.
- **No WebSocket / real-time updates.**  Dashboard stats are fetched via polling (React Query).  There are no Server-Sent Events or WebSocket pushes for live user status changes.
- **OpenVPN management socket is single-instance.**  Only one OpenVPN process's management interface is monitored.  If you run multiple OpenVPN server instances, only the one at `OPENVPN_MANAGEMENT_SOCKET` is managed by the panel.
- **Subscription token is not revocable via blacklist.**  Old tokens are invalidated by replacing the token value in the DB.  If a client caches an old `.ovpn` file, they can still connect until the cert is revoked or expires — the subscription URL is just a delivery mechanism, not an access control layer.
- **No automated cert renewal.**  Client certificates do not auto-renew.  Operators must manually revoke and recreate certs before they expire.
- **Telegram bot is notification-only.**  It does not support interactive commands (e.g., `/status user1`).  It only sends outbound notifications for enforcement events and admin actions.

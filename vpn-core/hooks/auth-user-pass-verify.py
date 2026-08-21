#!/usr/bin/env python3
"""
auth-user-pass-verify.py — OpenVPN auth-user-pass-verify hook.

Reads username/password from stdin (provided by OpenVPN when a client
sends auth-user-pass credentials) and validates against the eovpanel
database.  Rejects disabled/expired/limited/over-limit users even
if their certificate is still valid.

Exit 0 = allow, exit 1 = deny.

When no ovpn_password is set for the user, any password is accepted
(cert-only auth).  When ovpn_password IS set, it must match exactly.

Environment variables provided by OpenVPN:
  $common_name   — CN from the client certificate
  $script_type   — "auth-user-pass-verify"
"""

import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone


DB_PATH = os.environ.get("EOVPANEL_DB_PATH", "/opt/eovpanel/data/eovpanel.db")
LOG_FILE = "/var/log/openvpn-hooks.log"


def log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [auth] {msg}\n")
    except OSError:
        pass


def main() -> int:
    # Read username and password from stdin (OpenVPN sends them line-by-line)
    lines = sys.stdin.read().strip().split("\n")
    if len(lines) < 2:
        log("DENIED: No credentials provided (stdin empty or incomplete).")
        return 1

    username = lines[0].strip()
    password = lines[1].strip()

    if not username:
        log("DENIED: Empty username.")
        return 1

    if not os.path.exists(DB_PATH):
        log(f"ERROR: Database not found at {DB_PATH}, allowing connection.")
        return 0

    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            "SELECT status, expire_at, data_limit, data_used, ovpn_password "
            "FROM users WHERE username = ? AND revoked = 0",
            (username,),
        )
        row = cur.fetchone()
        conn.close()
    except Exception as exc:
        log(f"ERROR: Database query failed: {exc}, allowing connection.")
        return 0

    if row is None:
        log(f"DENIED: User '{username}' not found or revoked.")
        return 1

    status = row["status"]
    expire_at = row["expire_at"]
    data_limit = row["data_limit"]
    data_used = row["data_used"]
    ovpn_password = row["ovpn_password"] or ""

    # Check status — reject disabled, expired, limited
    if status in ("disabled", "expired", "limited"):
        log(f"DENIED: User '{username}' has status '{status}'.")
        return 1

    # Check expiry
    if expire_at:
        try:
            exp_dt = datetime.fromisoformat(expire_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                log(f"DENIED: User '{username}' expired at {expire_at}.")
                return 1
        except (ValueError, TypeError):
            pass

    # Check data limit
    if data_limit and data_limit > 0 and data_used >= data_limit:
        log(f"DENIED: User '{username}' over data limit ({data_used}/{data_limit}).")
        return 1

    # Check password — if ovpn_password is set, it must match
    if ovpn_password:
        if password != ovpn_password:
            log(f"DENIED: User '{username}' password mismatch.")
            return 1
    # If no ovpn_password set, any password is accepted (cert-only auth)

    log(f"ALLOWED: User '{username}' authenticated (status={status}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

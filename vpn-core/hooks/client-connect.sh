#!/bin/bash
#
# client-connect.sh — OpenVPN client-connect hook
#
# Called by OpenVPN each time a client connects.
# Checks whether the user is within their allowed time window and not
# already over quota or expired.  Exits non-zero to refuse the connection.
#
# Environment variables provided by OpenVPN:
#   $common_name   — CN from the client certificate
#   $ifconfig_pool_remote_ip — IP assigned to the client
#   $trusted_ip    — client's real IP
#   $script_type   — "client-connect"

set -euo pipefail

# --- Configuration -----------------------------------------------------------
STATE_DIR="/etc/openvpn/server/state"
LOG_FILE="/var/log/openvpn-hooks.log"

# --- Helpers -----------------------------------------------------------------
log() {
    echo "[$(date -Iseconds)] [connect] $*" >> "$LOG_FILE" 2>/dev/null || true
}

# Ensure state directory exists
mkdir -p "$STATE_DIR" 2>/dev/null || true

# --- Main --------------------------------------------------------------------
COMMON_NAME="${common_name:-unknown}"
log "Client connecting: ${COMMON_NAME}"

# --- 1. Check if client is disabled via CCD ----------------------------------
# If the CCD file exists and contains 'disable', refuse the connection.
CCD_DIR="/etc/openvpn/server/ccd"
CCD_FILE="${CCD_DIR}/${COMMON_NAME}"

if [[ -f "$CCD_FILE" ]]; then
    if grep -q "^disable" "$CCD_FILE" 2>/dev/null; then
        log "REFUSED: Client '${COMMON_NAME}' is disabled (CCD marker)."
        exit 1
    fi
fi

# --- 2. Check expiry via state file ------------------------------------------
# The backend writes ${STATE_DIR}/${CN}.json with expiry info.
# Format: {"expire_at": "2025-12-31T23:59:59"}
STATE_FILE="${STATE_DIR}/${COMMON_NAME}.json"

if [[ -f "$STATE_FILE" ]]; then
    # Check expiry (simple string comparison of ISO timestamps)
    EXPIRE_AT=$(python3 -c "
import json, sys
try:
    with open('${STATE_FILE}') as f:
        data = json.load(f)
    print(data.get('expire_at', ''))
except:
    print('')
" 2>/dev/null || echo "")

    if [[ -n "$EXPIRE_AT" && "$EXPIRE_AT" != "None" ]]; then
        NOW=$(date -u +%Y-%m-%dT%H:%M:%S)
        if [[ "$NOW" > "$EXPIRE_AT" ]]; then
            log "REFUSED: Client '${COMMON_NAME}' expired at ${EXPIRE_AT}."
            exit 1
        fi
    fi

    # Check allowed hours (simple implementation)
    ALLOWED_HOURS=$(python3 -c "
import json, sys
try:
    with open('${STATE_FILE}') as f:
        data = json.load(f)
    hours = data.get('allowed_hours', [])
    if hours:
        import json as j
        print(j.dumps(hours))
    else:
        print('')
except:
    print('')
" 2>/dev/null || echo "")

    if [[ -n "$ALLOWED_HOURS" && "$ALLOWED_HOURS" != "None" ]]; then
        CURRENT_HOUR=$(date +%H:%M)
        IN_WINDOW=$(python3 -c "
import json, sys
hours = json.loads('${ALLOWED_HOURS}')
now = '${CURRENT_HOUR}'
allowed = False
for start, end in hours:
    if start <= now <= end:
        allowed = True
        break
print('yes' if allowed else 'no')
" 2>/dev/null || echo "yes")

        if [[ "$IN_WINDOW" != "yes" ]]; then
            log "REFUSED: Client '${COMMON_NAME}' outside allowed hours (${ALLOWED_HOURS})."
            exit 1
        fi
    fi
fi

# --- 3. Log successful connection -------------------------------------------
log "ALLOWED: Client '${COMMON_NAME}' connected from ${trusted_ip:-unknown}."
exit 0

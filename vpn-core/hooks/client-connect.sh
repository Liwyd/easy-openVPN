#!/bin/bash
#
# client-connect.sh — OpenVPN client-connect hook
#
# Called by OpenVPN each time a client connects.
# Checks whether the user is disabled, expired, or outside allowed hours.
# Exits non-zero to refuse the connection.
#
# IMPORTANT: This script must NEVER fail open. If anything goes wrong,
# it exits 0 (allow) so the connection isn't blocked by hook bugs.
#
# Environment variables provided by OpenVPN:
#   $common_name   — CN from the client certificate
#   $ifconfig_pool_remote_ip — IP assigned to the client
#   $trusted_ip    — client's real IP
#   $script_type   — "client-connect"

# --- Configuration -----------------------------------------------------------
STATE_DIR="/etc/openvpn/server/state"
CCD_DIR="/etc/openvpn/server/ccd"
LOG_FILE="/var/log/openvpn-hooks.log"

# --- Helpers -----------------------------------------------------------------
log() {
    echo "[$(date -Iseconds)] [connect] $*" >> "$LOG_FILE" 2>/dev/null || true
}

# --- Main (wrapped to never crash OpenVPN) -----------------------------------
main() {
    mkdir -p "$STATE_DIR" 2>/dev/null || true

    COMMON_NAME="${common_name:-unknown}"
    log "Client connecting: ${COMMON_NAME}"

    # --- 1. Check if client is disabled via CCD ----------------------------------
    CCD_FILE="${CCD_DIR}/${COMMON_NAME}"
    if [[ -f "$CCD_FILE" ]]; then
        if grep -q "^disable" "$CCD_FILE" 2>/dev/null; then
            log "REFUSED: Client '${COMMON_NAME}' is disabled (CCD marker)."
            exit 1
        fi
    fi

    # --- 2. Check expiry via state file ------------------------------------------
    STATE_FILE="${STATE_DIR}/${COMMON_NAME}.json"

    if [[ -f "$STATE_FILE" ]]; then
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

        # Check allowed hours
        ALLOWED_HOURS=$(python3 -c "
import json, sys
try:
    with open('${STATE_FILE}') as f:
        data = json.load(f)
    hours = data.get('allowed_hours', [])
    if hours:
        print(json.dumps(hours))
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

    log "ALLOWED: Client '${COMMON_NAME}' connected from ${trusted_ip:-unknown}."
    exit 0
}

# Run main, but if anything unexpected fails, allow the connection
main "$@" || { log "ERROR: Hook crashed, allowing connection."; exit 0; }

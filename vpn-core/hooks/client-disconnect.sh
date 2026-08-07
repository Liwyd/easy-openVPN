#!/bin/bash
#
# client-disconnect.sh — OpenVPN client-disconnect hook
#
# Called by OpenVPN each time a client disconnects.
# Logs the disconnect event.  Heavy accounting is handled by the periodic
# status_reader job in the backend (stage 4+).
#
# Environment variables provided by OpenVPN:
#   $common_name   — CN from the client certificate
#   $bytes_received — total bytes received from client
#   $bytes_sent     — total bytes sent to client
#   $trusted_ip    — client's real IP
#   $script_type   — "client-disconnect"

set -euo pipefail

# --- Configuration -----------------------------------------------------------
STATE_DIR="/etc/openvpn/server/state"
LOG_FILE="/var/log/openvpn-hooks.log"

# --- Helpers -----------------------------------------------------------------
log() {
    echo "[$(date -Iseconds)] [disconnect] $*" >> "$LOG_FILE" 2>/dev/null || true
}

# Ensure state directory exists
mkdir -p "$STATE_DIR" 2>/dev/null || true

# --- Main --------------------------------------------------------------------
COMMON_NAME="${common_name:-unknown}"
BYTES_RECEIVED="${bytes_received:-0}"
BYTES_SENT="${bytes_sent:-0}"
TRUSTED_IP="${trusted_ip:-unknown}"

log "Client disconnected: ${COMMON_NAME} from ${TRUSTED_IP} — rx=${BYTES_RECEIVED} tx=${BYTES_SENT}"

# --- Update session state file -----------------------------------------------
# Write the last-seen timestamp and byte counters to the state file.
# The backend can read this for quick per-user accounting.
STATE_FILE="${STATE_DIR}/${COMMON_NAME}.json"

if [[ -f "$STATE_FILE" ]]; then
    # Update existing state file with disconnect info
    python3 -c "
import json, sys
try:
    with open('${STATE_FILE}') as f:
        data = json.load(f)
except:
    data = {}

data['last_disconnect'] = '$(date -Iseconds)'
data['last_bytes_received'] = int('${BYTES_RECEIVED}')
data['last_bytes_sent'] = int('${BYTES_SENT}')
data['last_trusted_ip'] = '${TRUSTED_IP}'

with open('${STATE_FILE}', 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null || true
fi

exit 0

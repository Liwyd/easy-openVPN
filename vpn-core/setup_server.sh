#!/bin/bash
#
# setup_server.sh — Idempotent OpenVPN server bootstrap
#
# Adapted from Nyr's openvpn-install script:
# https://github.com/Nyr/openvpn-install
#
# Copyright (c) 2013 Nyr. Released under the MIT License.
#
# This script installs OpenVPN + easy-rsa, generates CA/server certs,
# creates a baseline server.conf, enables IP forwarding, sets up NAT,
# and starts the OpenVPN systemd service. It is idempotent — safe to
# run multiple times without duplicating work.
#
# Usage: ./setup_server.sh <interface> <port> <protocol>
#   interface  – network interface for NAT (e.g. eth0, ens3)
#   port       – UDP/TCP port to listen on (default: 1194)
#   protocol   – udp or tcp (default: udp)

set -euo pipefail

# --- Configuration -----------------------------------------------------------
INTERFACE="${1:-}"
PORT="${2:-1194}"
PROTOCOL="${3:-udp}"
EASYRSA_VERSION="3.2.6"
EASYRSA_DIR="/etc/openvpn/server/easy-rsa"
SERVER_DIR="/etc/openvpn/server"
VPN_SUBNET="10.8.0.0"
VPN_MASK="255.255.255.0"
CCD_DIR="${SERVER_DIR}/ccd"
HOOKS_DIR="/etc/openvpn/server/hooks"
STATUS_LOG="${SERVER_DIR}/status.log"

# --- Helpers -----------------------------------------------------------------
die() { echo "ERROR: $*" >&2; exit 1; }

need_root() {
    [[ $EUID -eq 0 ]] || die "This script must be run as root."
}

detect_os() {
    if grep -qs "ubuntu" /etc/os-release; then
        OS="ubuntu"
    elif [[ -e /etc/debian_version ]]; then
        OS="debian"
    elif [[ -e /etc/almalinux-release || -e /etc/rocky-release || -e /etc/centos-release ]]; then
        OS="centos"
    elif [[ -e /etc/fedora-release ]]; then
        OS="fedora"
    else
        die "Unsupported distribution. Supported: Ubuntu, Debian, AlmaLinux, Rocky, CentOS, Fedora."
    fi
}

detect_group() {
    if [[ "$OS" == "debian" || "$OS" == "ubuntu" ]]; then
        GROUP="nogroup"
    else
        GROUP="nobody"
    fi
}

# --- Package installation ----------------------------------------------------
install_packages() {
    echo "[*] Installing packages..."
    if [[ "$OS" == "debian" || "$OS" == "ubuntu" ]]; then
        apt-get update -qq
        apt-get install -y --no-install-recommends openvpn openssl ca-certificates iptables
    elif [[ "$OS" == "centos" ]]; then
        dnf install -y epel-release
        dnf install -y openvpn openssl ca-certificates tar iptables
    else
        dnf install -y openvpn openssl ca-certificates tar iptables
    fi
}

# --- easy-rsa bootstrap ------------------------------------------------------
setup_easyrsa() {
    if [[ -d "${EASYRSA_DIR}/pki" ]]; then
        echo "[*] easy-rsa PKI already exists, skipping init."
        return 0
    fi

    echo "[*] Downloading easy-rsa ${EASYRSA_VERSION}..."
    mkdir -p "$EASYRSA_DIR"
    local url="https://github.com/OpenVPN/easy-rsa/releases/download/v${EASYRSA_VERSION}/EasyRSA-${EASYRSA_VERSION}.tgz"
    wget -qO- "$url" 2>/dev/null | tar xz -C "$EASYRSA_DIR" --strip-components 1
    chown -R root:root "$EASYRSA_DIR"

    echo "[*] Initialising PKI..."
    cd "$EASYRSA_DIR"
    ./easyrsa --batch init-pki
    ./easyrsa --batch build-ca nopass
    ./easyrsa gen-tls-crypt-key

    # DH parameters (ffdhe2048)
    cat > "${SERVER_DIR}/dh.pem" <<'DHPARAM'
-----BEGIN DH PARAMETERS-----
MIIBCAKCAQEA//////////+t+FRYortKmq/cViAnPTzx2LnFg84tNpWp4TZBFGQz
+8yTnc4kmz75fS/jY2MMddj2gbICrsRhetPfHtXV/WVhJDP1H18GbtCFY2VVPe0a
87VXE15/V8k1mE8McODmi3fipona8+/och3xWKE2rec1MKzKT0g6eXq8CrGCsyT7
YdEIqUuyyOP7uWrat2DX9GgdT0Kj3jlN9K5W7edjcrsZCwenyO4KbXCeAvzhzffi
7MA0BM0oNC9hkXL+nOmFg/+OTxIy7vKBg8P+OxtMb61zO7X8vC7CIAXFjvGDfRaD
ssbzSibBsu/6iGtCOGEoXJf//////////wIBAg==
-----END DH PARAMETERS-----
DHPARAM
    ln -sf "${SERVER_DIR}/dh.pem" pki/dh.pem

    echo "[*] Generating server certificate..."
    ./easyrsa --batch --days=3650 build-server-full server nopass
    ./easyrsa --batch --days=3650 gen-crl

    # Copy artefacts to server dir
    cp pki/ca.crt pki/private/ca.key pki/issued/server.crt pki/private/server.key pki/crl.pem "$SERVER_DIR"
    cp pki/private/easyrsa-tls.key "${SERVER_DIR}/tc.key"

    chown nobody:"${GROUP}" "${SERVER_DIR}/crl.pem"
    chmod o+x "$SERVER_DIR"
}

# --- IP forwarding & NAT -----------------------------------------------------
setup_network() {
    echo "[*] Enabling IP forwarding..."
    echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-openvpn-forward.conf
    sysctl -w net.ipv4.ip_forward=1 >/dev/null

    local iptables_path
    iptables_path=$(command -v iptables)

    echo "[*] Setting up NAT rule..."
    # Remove old rule if present, then add fresh
    "$iptables_path" -w 5 -t nat -D POSTROUTING -s "${VPN_SUBNET}/24" ! -d "${VPN_SUBNET}/24" -j SNAT --to "$PUBLIC_IP" 2>/dev/null || true
    "$iptables_path" -w 5 -t nat -A POSTROUTING -s "${VPN_SUBNET}/24" ! -d "${VPN_SUBNET}/24" -j SNAT --to "$PUBLIC_IP"

    # Create persistent iptables systemd service
    cat > /etc/systemd/system/openvpn-iptables.service <<UNIT
[Unit]
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=${iptables_path} -w 5 -t nat -A POSTROUTING -s ${VPN_SUBNET}/24 ! -d ${VPN_SUBNET}/24 -j SNAT --to ${PUBLIC_IP}
ExecStart=${iptables_path} -w 5 -I INPUT -p ${PROTOCOL} --dport ${PORT} -j ACCEPT
ExecStart=${iptables_path} -w 5 -I FORWARD -s ${VPN_SUBNET}/24 -j ACCEPT
ExecStart=${iptables_path} -w 5 -I FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
ExecStop=${iptables_path} -w 5 -t nat -D POSTROUTING -s ${VPN_SUBNET}/24 ! -d ${VPN_SUBNET}/24 -j SNAT --to ${PUBLIC_IP}
ExecStop=${iptables_path} -w 5 -D INPUT -p ${PROTOCOL} --dport ${PORT} -j ACCEPT
ExecStop=${iptables_path} -w 5 -D FORWARD -s ${VPN_SUBNET}/24 -j ACCEPT
ExecStop=${iptables_path} -w 5 -D FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
UNIT
    systemctl enable --now openvpn-iptables.service
}

# --- Detect public IP ---------------------------------------------------------
detect_public_ip() {
    # Try to get public IP
    PUBLIC_IP=$(wget -T 5 -t 1 -4qO- "http://ip1.dynupdate.no-ip.com/" 2>/dev/null \
        || curl -m 5 -4Ls "http://ip1.dynupdate.no-ip.com/" 2>/dev/null \
        || echo "")
    if [[ -z "$PUBLIC_IP" ]]; then
        # Fallback: use the IP on the specified interface
        PUBLIC_IP=$(ip -4 addr show "$INTERFACE" | grep -oE '[0-9]{1,3}(\.[0-9]{1,3}){3}' | head -1)
    fi
    [[ -n "$PUBLIC_IP" ]] || die "Could not detect public IP address."
    echo "[*] Public IP: ${PUBLIC_IP}"
}

# --- CCD directory -----------------------------------------------------------
setup_ccd() {
    mkdir -p "$CCD_DIR"
    mkdir -p "$HOOKS_DIR"
}

# --- Generate baseline server.conf -------------------------------------------
# The full server.conf is rendered by config_writer.py from the DB row.
# This script only creates the initial file if one doesn't exist yet.
generate_initial_server_conf() {
    if [[ -f "${SERVER_DIR}/server.conf" ]]; then
        echo "[*] server.conf already exists, skipping initial generation."
        return 0
    fi

    echo "[*] Generating initial server.conf..."
    cat > "${SERVER_DIR}/server.conf" <<CONF
# eovpanel — OpenVPN server configuration
# Generated by setup_server.sh on $(date -Iseconds)
# Further edits should be done through the panel or config_writer.py

port ${PORT}
proto ${PROTOCOL}
dev tun

ca ca.crt
cert server.crt
key server.key
dh dh.pem

cipher AES-256-GCM
auth SHA256
tls-crypt tc.key
topology subnet
server ${VPN_SUBNET} ${VPN_MASK}

push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 1.1.1.1"
push "dhcp-option DNS 1.0.0.1"
push "block-outside-dns"

ifconfig-pool-persist ipp.txt
keepalive 10 120

user nobody
group ${GROUP}
persist-key
persist-tun

status ${STATUS_LOG} 60
verb 3

# Management interface (unix socket)
management /run/openvpn/management.sock unix

# Allow external scripts (hooks, CCD)
script-security 2

# Client-config-dir for per-client overrides
client-config-dir ${CCD_DIR}

# Scripts
client-connect ${HOOKS_DIR}/client-connect.sh
client-disconnect ${HOOKS_DIR}/client-disconnect.sh

crl-verify crl.pem
CONF

    if [[ "$PROTOCOL" == "udp" ]]; then
        echo "explicit-exit-notify" >> "${SERVER_DIR}/server.conf"
    fi

    # Generate client-common.txt as a template for manual easy-rsa workflows
    cat > "${SERVER_DIR}/client-common.txt" <<'CLIENTCONF'
client
dev tun
proto PROTOCOL_PLACEHOLDER
remote IP_PLACEHOLDER PORT_PLACEHOLDER
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-GCM
auth SHA256
ignore-unknown-option block-outside-dns
verb 3
CLIENTCONF
    sed -i "s/PROTOCOL_PLACEHOLDER/${PROTOCOL}/" "${SERVER_DIR}/client-common.txt"
    sed -i "s/IP_PLACEHOLDER/${PUBLIC_IP}/" "${SERVER_DIR}/client-common.txt"
    sed -i "s/PORT_PLACEHOLDER/${PORT}/" "${SERVER_DIR}/client-common.txt"
}

# --- Copy hook scripts -------------------------------------------------------
install_hooks() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    mkdir -p "$HOOKS_DIR"

    if [[ -f "${script_dir}/hooks/client-connect.sh" ]]; then
        cp "${script_dir}/hooks/client-connect.sh" "${HOOKS_DIR}/client-connect.sh"
        chmod +x "${HOOKS_DIR}/client-connect.sh"
    fi
    if [[ -f "${script_dir}/hooks/client-disconnect.sh" ]]; then
        cp "${script_dir}/hooks/client-disconnect.sh" "${HOOKS_DIR}/client-disconnect.sh"
        chmod +x "${HOOKS_DIR}/client-disconnect.sh"
    fi
}

# --- Enable and start OpenVPN ------------------------------------------------
enable_service() {
    echo "[*] Enabling OpenVPN service..."
    systemctl enable --now openvpn-server@server.service
    echo "[+] OpenVPN server started."
}

# --- Main --------------------------------------------------------------------
main() {
    [[ -z "$INTERFACE" ]] && die "Usage: $0 <interface> [port] [protocol]"
    need_root
    detect_os
    detect_group
    detect_public_ip

    # If server.conf already exists, we're done (idempotent)
    if [[ -f "${SERVER_DIR}/server.conf" ]]; then
        echo "[*] OpenVPN server already configured at ${SERVER_DIR}/server.conf"
        echo "[*] To reconfigure, remove ${SERVER_DIR}/server.conf and re-run."
        return 0
    fi

    install_packages
    setup_easyrsa
    setup_network
    setup_ccd
    generate_initial_server_conf
    install_hooks
    enable_service

    echo "[+] Server setup complete."
    echo "    Config:  ${SERVER_DIR}/server.conf"
    echo "    Easy-RSA: ${EASYRSA_DIR}"
    echo "    CCD:     ${CCD_DIR}"
    echo "    Hooks:   ${HOOKS_DIR}"
}

main "$@"

#!/usr/bin/env bash
#
# bootstrap.sh — One-liner installer for eovpanel
#
# Usage:
#   sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Liwyd/easy-openVPN/main/installer/bootstrap.sh)"
#
# What it does:
#   1. Checks for root privileges
#   2. Installs Python 3.12+ if not present
#   3. Clones (or updates) the repo to /opt/eovpanel
#   4. Installs the TUI installer package
#   5. Launches the Textual-based installer

set -euo pipefail

REPO_URL="https://github.com/Liwyd/easy-openVPN.git"
REPO_DIR="/opt/eovpanel"
INSTALLER_DIR="${REPO_DIR}/installer"
VENV_DIR="${REPO_DIR}/.venv-installer"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[*]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*" >&2; }
die()   { error "$*"; exit 1; }

# --- Root check ---------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    die "This script must be run as root. Re-run with: sudo bash -c \"\$(curl -fsSL ...)\""
fi

# --- Detect OS ----------------------------------------------------------------
detect_os() {
    if grep -qs "ubuntu" /etc/os-release 2>/dev/null; then
        OS="ubuntu"
    elif [[ -e /etc/debian_version ]]; then
        OS="debian"
    else
        die "Unsupported distribution. This installer requires Ubuntu or Debian."
    fi
}
detect_os
info "Detected OS: ${OS}"

# --- Install Python 3.12+ if needed ------------------------------------------
install_python() {
    if command -v python3 &>/dev/null; then
        PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

        if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 12 ]]; then
            info "Python ${PY_VERSION} found."
            return 0
        fi
    fi

    info "Python 3.12+ not found. Installing..."
    apt-get update -qq
    apt-get install -y --no-install-recommends software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq
    apt-get install -y --no-install-recommends python3.12 python3.12-venv python3-pip
    info "Python 3.12 installed."
}

# --- Install dependencies for Textual ----------------------------------------
install_system_deps() {
    info "Installing system dependencies..."
    apt-get install -y --no-install-recommends \
        git curl wget ca-certificates \
        libffi-dev libssl-dev

    # Textual needs these for the TUI
    apt-get install -y --no-install-recommends \
        python3-dev build-essential || true
}

# --- Clone or update repo -----------------------------------------------------
clone_repo() {
    if [[ -d "${REPO_DIR}/.git" ]]; then
        info "Repository already exists at ${REPO_DIR}. Updating..."
        cd "${REPO_DIR}"
        git pull --ff-only || warn "Could not pull latest. Using existing version."
    else
        info "Cloning repository..."
        git clone "${REPO_URL}" "${REPO_DIR}"
    fi
}

# --- Set up Python venv and install installer ----------------------------------
setup_venv() {
    info "Setting up Python virtual environment..."

    if [[ ! -d "${VENV_DIR}" ]]; then
        python3 -m venv "${VENV_DIR}"
    fi

    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"

    info "Installing installer dependencies..."
    pip install --quiet --upgrade pip
    pip install --quiet "${INSTALLER_DIR}"

    info "Installer package installed."
}

# --- Launch the TUI -----------------------------------------------------------
launch_installer() {
    info "Launching eovpanel installer..."
    echo ""
    echo "  ┌─────────────────────────────────────────────┐"
    echo "  │  Use arrow keys to navigate, Enter to      │"
    echo "  │  select, 'q' to quit at any time.          │"
    echo "  └─────────────────────────────────────────────┘"
    echo ""

    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    eovpanel-installer
}

# --- Main ---------------------------------------------------------------------
main() {
    echo ""
    echo "  ╔═══════════════════════════════════════════════╗"
    echo "  ║       eovpanel Installer Bootstrap            ║"
    echo "  ║       OpenVPN Management Panel                ║"
    echo "  ╚═══════════════════════════════════════════════╝"
    echo ""

    install_python
    install_system_deps
    clone_repo
    setup_venv
    launch_installer
}

main "$@"

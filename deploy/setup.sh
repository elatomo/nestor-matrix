#!/usr/bin/env bash
# deploy/setup.sh - Initial server setup for Néstor Matrix Bot
#
# Target: Debian 12+ (Bookworm) / Ubuntu 22.04+
# Architecture: ARM64 (aarch64) or x86_64
# Run as: root or with sudo
#
# Prerequisites (assumed):
#   - SSH access configured
#   - Firewall configured (if any)
#   - Matrix homeserver running and accessible
#
# Usage:
#   scp deploy/setup.sh your-vps:/tmp/ && ssh your-vps 'sudo bash /tmp/setup.sh'

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

readonly APP_USER="nestor"
readonly APP_DIR="/opt/nestor-matrix"
readonly REPO_URL="https://github.com/elatomo/nestor-matrix.git"
readonly SERVICE_NAME="nestor-matrix"

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

log() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

check_root() {
    [[ $EUID -eq 0 ]] || err "This script must be run as root (use sudo)"
}

check_os() {
    if [[ ! -f /etc/debian_version ]]; then
        err "This script targets Debian/Ubuntu only"
    fi
    log "Detected: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
}

# ---------------------------------------------------------------------------
# Installation Steps
# ---------------------------------------------------------------------------

install_dependencies() {
    log "Installing system dependencies"
    apt-get update -qq
    apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        curl \
        build-essential cmake  # Build deps for python-olm (E2EE)
}

create_user() {
    log "Creating application user: $APP_USER"

    if id "$APP_USER" &>/dev/null; then
        log "User $APP_USER already exists, skipping"
        return
    fi

    adduser \
        --system \
        --home "$APP_DIR" \
        --shell /bin/bash \
        --group \
        --disabled-password \
        "$APP_USER"
}

install_uv() {
    log "Installing uv package manager"

    local uv_bin="$APP_DIR/.local/bin/uv"

    if [[ -x "$uv_bin" ]]; then
        log "uv already installed: $($uv_bin --version)"
        return
    fi

    # Install uv as the app user (installs to ~/.local/bin)
    sudo -u "$APP_USER" bash -c \
        'curl -LsSf https://astral.sh/uv/install.sh | sh'

    log "uv installed: $($uv_bin --version)"
}

clone_repository() {
    log "Setting up application repository"

    local repo_dir="$APP_DIR/repo"

    if [[ -d "$repo_dir/.git" ]]; then
        log "Repository exists, pulling latest"
        sudo -u "$APP_USER" git -C "$repo_dir" pull --ff-only origin main
    else
        log "Cloning repository"
        sudo -u "$APP_USER" git clone "$REPO_URL" "$repo_dir"
    fi
}

setup_python_environment() {
    log "Setting up Python environment"

    local repo_dir="$APP_DIR/repo"
    local uv_bin="$APP_DIR/.local/bin/uv"

    cd "$repo_dir"

    # uv automatically downloads the Python version from .python-version
    # --frozen: use exact versions from uv.lock
    sudo -u "$APP_USER" "$uv_bin" sync --frozen

    log "Python environment ready"
    sudo -u "$APP_USER" "$uv_bin" run python --version
}

setup_env_file() {
    log "Setting up environment file"

    local env_file="$APP_DIR/repo/.env"
    local env_example="$APP_DIR/repo/.env.example"

    if [[ -f "$env_file" ]]; then
        log ".env already exists, skipping (preserving secrets)"
        return
    fi

    if [[ ! -f "$env_example" ]]; then
        err ".env.example not found in repository"
    fi

    sudo -u "$APP_USER" cp "$env_example" "$env_file"

    # Restrict permissions: owner read/write only
    chmod 600 "$env_file"

    log "Created .env from template - YOU MUST EDIT THIS FILE"
}

install_systemd_service() {
    log "Installing systemd service"

    local service_src="$APP_DIR/repo/deploy/$SERVICE_NAME.service"
    local service_dst="/etc/systemd/system/$SERVICE_NAME.service"

    if [[ ! -f "$service_src" ]]; then
        err "Service file not found: $service_src"
    fi

    cp "$service_src" "$service_dst"
    chmod 644 "$service_dst"

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"

    log "Service installed and enabled (not started)"
}

print_next_steps() {
    cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Setup complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next steps:

1. Edit the environment file with your secrets:

   sudo -u $APP_USER vi $APP_DIR/repo/.env

2. Required values:
   - HOMESERVER_URL: Your Matrix server, e.g., https://matrix.example.com
   - USER_ID: Bot's Matrix ID, e.g., @nestor:example.com
   - ACCESS_TOKEN: From: sudo -u $APP_USER uv run nestor-matrix login
   - DEVICE_ID: From login command above
   - PICKLE_KEY: From: sudo -u $APP_USER uv run nestor-matrix generate-pickle-key
   - NESTOR_OPENAI_API_KEY

3. Start the service:

   sudo systemctl start $SERVICE_NAME

4. Check status:

   sudo systemctl status $SERVICE_NAME
   journalctl -u $SERVICE_NAME -f

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    log "Néstor Matrix Bot - Server Setup"

    check_root
    check_os

    install_dependencies
    create_user
    install_uv
    clone_repository
    setup_python_environment
    setup_env_file
    install_systemd_service

    print_next_steps
}

main "$@"

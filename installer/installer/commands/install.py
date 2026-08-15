"""Install command — full end-to-end installation with inline progress."""

from __future__ import annotations

import os
import shutil
import sys

from installer.output import (
    banner, bold, confirm, dim, fail, green, heading, info, ok, prompt_secret,
    prompt_secret_required, prompt_str, prompt_str_required, step, warn, yellow,
)
from installer.utils import (
    COMPOSE_FILE, DOCKER_ENV, ESSL_CERT_DIR, ENV_FILE, REPO_ENV, REPO_ROOT,
    VPN_CORE, detect_default_interface, detect_os, detect_public_ip,
    docker_compose_pull, docker_compose_up, docker_running, generate_jwt_secret,
    openvpn_installed, read_env, run_cmd, seed_backend_admin, write_env,
)

TOTAL_STEPS = 5


def cmd_install(args) -> None:
    """Run the full installation pipeline."""
    banner()

    # ── Pre-flight: idempotency check ──────────────────────────────────
    if ENV_FILE.exists():
        env = read_env()
        if env.get("JWT_SECRET_KEY") and env["JWT_SECRET_KEY"] != "changeme-in-production":
            warn("An existing installation was detected.")
            if not confirm("Re-run the install and overwrite the existing config?", default=False):
                info("Aborted. Run `eovpanel configure` to modify settings.")
                return

    # ── Step 0: System check ───────────────────────────────────────────
    step(1, TOTAL_STEPS, "System check")
    os_info = detect_os()
    info(f"OS: {os_info.distro} {os_info.version}")
    info(f"Root: {'yes' if os_info.is_root else 'no'}")

    if not os_info.is_root:
        fail("Installer must be run as root.")
        fail("Re-run with: sudo bash -c \"$(curl -fsSL ...)\"")
        sys.exit(1)

    if not os_info.is_debian_like:
        warn(f"Only Ubuntu/Debian is officially supported. Detected: {os_info.distro}")

    if openvpn_installed():
        warn("Existing OpenVPN installation detected.")
        if not confirm("Reuse the existing OpenVPN setup?", default=True):
            info("Aborted.")
            return
    else:
        ok("No existing OpenVPN found. Will install from scratch.")

    # ── Step 1: VPN settings ───────────────────────────────────────────
    step(2, TOTAL_STEPS, "VPN settings")
    detected_ip = detect_public_ip()
    detected_iface = detect_default_interface()

    if args.non_interactive:
        vpn_port = args.port
        vpn_protocol = args.protocol
        public_ip = detected_ip
        iface = detected_iface
    else:
        vpn_port = prompt_str("VPN port", str(args.port))
        vpn_protocol = prompt_str("Protocol (udp/tcp)", args.protocol)
        public_ip = prompt_str("Public IP / hostname", detected_ip or "")
        iface = prompt_str("Network interface", detected_iface)

    info(f"Port: {vpn_port}")
    info(f"Protocol: {vpn_protocol}")
    info(f"Public IP: {public_ip or '(will auto-detect)'}")
    info(f"Interface: {iface}")

    # Panel host port — Marzban-style: this single port serves the frontend,
    # the API, and the subscription page. The backend is proxied internally
    # by nginx (no separate backend port exposed on the host).
    panel_port = args.panel_port
    if not args.non_interactive:
        panel_port = prompt_str("Panel host port", panel_port)
    info(f"Panel host port: {panel_port}")

    # Optional base path — serves the panel only under /<path> so internet
    # scanners hitting the root get a 404. Empty = panel at the root.
    panel_path = args.panel_path
    if not args.non_interactive:
        panel_path = prompt_str(
            "Panel path (optional, e.g. dashboard)", panel_path
        )
    panel_path = panel_path.strip().strip("/")
    if panel_path:
        info(f"Panel path: /{panel_path} (root returns 404)")
    else:
        info("Panel path: none (served at root)")

    # ── Step 2: Admin account ──────────────────────────────────────────
    step(3, TOTAL_STEPS, "Admin account")
    if args.non_interactive:
        admin_user = args.admin_user
        admin_pass = args.admin_pass
        if not admin_user:
            fail("Admin username cannot be empty. Use --admin-user to set one.")
            sys.exit(1)
        if not admin_pass:
            fail("Admin password cannot be empty. Use --admin-pass to set one.")
            sys.exit(1)
    else:
        admin_user = prompt_str_required("Admin username", args.admin_user)
        admin_pass = prompt_secret_required("Admin password")

    info(f"Admin user: {admin_user}")
    ok("Admin credentials ready.")

    # ── Step 3: Telegram (optional) ────────────────────────────────────
    step(4, TOTAL_STEPS, "Telegram (optional)")
    telegram_token = args.telegram_token
    telegram_chat = args.telegram_chat

    if not args.non_interactive and not telegram_token:
        if confirm("Enable Telegram bot notifications now?", default=False):
            telegram_token = prompt_str("Bot token", "")
            telegram_chat = prompt_str("Chat ID", "")

    if telegram_token:
        ok(f"Telegram bot enabled (chat ID: {telegram_chat})")
    else:
        info("Telegram skipped. You can enable it later from the panel Settings.")

    # ── Step 4: Domain & TLS (optional) ────────────────────────────────
    step(5, TOTAL_STEPS, "Domain & TLS")
    domain = args.domain
    email = args.email
    setup_tls = False

    if not args.non_interactive and not domain and not args.no_tls:
        if confirm("Set up a domain with free TLS certificate (via ESSL)?", default=False):
            domain = prompt_str("Domain name", "")
            email = prompt_str("Email (for Let's Encrypt)", "")
            if domain and email:
                setup_tls = True
            else:
                warn("Domain/email incomplete. Skipping TLS.")
    elif domain and email:
        setup_tls = True

    if setup_tls:
        info(f"Domain: {domain}")
        info(f"Email: {email}")
    else:
        info("TLS skipped. Panel will run over plain HTTP.")

    # ── Execute installation ───────────────────────────────────────────
    heading("Running installation")

    # 1. System packages
    info("Installing system packages...")
    rc, out = run_cmd(["apt-get", "update", "-qq"], stream=True)
    if rc != 0:
        fail("apt-get update failed")
        sys.exit(1)

    pkgs = ["openvpn", "openssl", "ca-certificates", "iptables", "curl", "wget", "git"]
    if not docker_running():
        pkgs.extend(["docker.io", "docker-compose-v2"])
    else:
        info("Docker already installed, skipping.")

    rc, out = run_cmd(["apt-get", "install", "-y", "--no-install-recommends"] + pkgs, stream=True)
    if rc != 0:
        fail("Package installation failed")
        sys.exit(1)

    # Ensure Docker compose V2 plugin is available
    rc, _ = run_cmd(["docker", "compose", "version"], timeout=10)
    if rc != 0:
        info("Docker Compose V2 plugin not found, installing...")
        rc, out = run_cmd(["apt-get", "install", "-y", "--no-install-recommends", "docker-compose-v2"], stream=True)
        if rc != 0:
            fail("Failed to install docker-compose-v2")
            sys.exit(1)
        ok("Docker Compose V2 installed.")

    # Ensure Docker daemon is running
    if not docker_running():
        info("Starting Docker daemon...")
        rc, _ = run_cmd(["systemctl", "enable", "--now", "docker"])
        if rc != 0:
            fail("Failed to start Docker daemon")
            sys.exit(1)
    ok("System packages installed.")

    # 2. OpenVPN server setup
    info("Setting up OpenVPN server...")
    setup_script = VPN_CORE / "setup_server.sh"
    if not setup_script.exists():
        fail(f"setup_server.sh not found at {setup_script}")
        sys.exit(1)

    rc, out = run_cmd(["bash", str(setup_script), iface, str(vpn_port), vpn_protocol], stream=True)
    if rc != 0:
        fail("OpenVPN server setup failed")
        sys.exit(1)
    ok("OpenVPN server configured.")

    # 3. Write backend .env
    info("Configuring backend environment...")
    env = read_env(ENV_FILE) if ENV_FILE.exists() else {}
    if not env.get("JWT_SECRET_KEY") or env["JWT_SECRET_KEY"] == "changeme-in-production":
        env["JWT_SECRET_KEY"] = generate_jwt_secret()
    env.setdefault("APP_NAME", "eovpanel")
    env.setdefault("APP_VERSION", "0.1.0")
    env.setdefault("DEBUG", "false")
    env.setdefault("HOST", "0.0.0.0")
    env.setdefault("PORT", "8000")
    env["PANEL_PORT"] = panel_port
    env["APP_BASE_PATH"] = f"/{panel_path}" if panel_path else ""
    # Docker compose mounts the named volume at /app/data; a bare ./eovpanel.db
    # would land in the container's writable layer (root-owned, lost on recreate).
    if env.get("DATABASE_URL", "") == "sqlite:///./eovpanel.db":
        env["DATABASE_URL"] = "sqlite:///./data/eovpanel.db"
    env.setdefault("DATABASE_URL", "sqlite:///./data/eovpanel.db")
    env.setdefault("JWT_ALGORITHM", "HS256")
    env.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    env.setdefault("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    env.setdefault("CORS_ORIGINS", "http://localhost,http://localhost:5173,http://localhost:3000")
    env.setdefault("OPENVPN_MANAGEMENT_SOCKET", "/run/openvpn/management.sock")
    env.setdefault("OPENVPN_STATUS_LOG", "/opt/eovpanel/vpn/status.log")
    env.setdefault("EASYRSA_DIR", "/opt/eovpanel/vpn/easy-rsa")
    # Panel backups live on the host so they survive container recreation.
    backup_dir = "/opt/eovpanel/backups"
    try:
        os.makedirs(backup_dir, exist_ok=True)
        # Match the uid:gid of `appuser` inside the container (uid 1000 by
        # default) so the bind-mounted directory is writable by the backend.
        run_cmd(["chown", "-R", "1000:1000", backup_dir])
    except OSError:
        backup_dir = "./backups"
    env["BACKUP_DIR"] = backup_dir
    if public_ip:
        env["PUBLIC_HOST"] = public_ip

    # Telegram
    if telegram_token:
        env["TELEGRAM_ENABLED"] = "true"
        env["TELEGRAM_BOT_TOKEN"] = telegram_token
        env["TELEGRAM_ADMIN_CHAT_IDS"] = telegram_chat
    else:
        env.setdefault("TELEGRAM_ENABLED", "false")
        env.setdefault("TELEGRAM_BOT_TOKEN", "")
        env.setdefault("TELEGRAM_ADMIN_CHAT_IDS", "")

    write_env(env, ENV_FILE)
    write_env(env, REPO_ENV)
    write_env(env, DOCKER_ENV)
    ok(f"Backend .env written to {ENV_FILE}")

    # 4. Seed admin
    info(f"Seeding admin account ({admin_user})...")
    seed_backend_admin(admin_user, admin_pass)
    ok("Admin account seeded.")

    # 5. TLS (optional)
    if setup_tls:
        info("Setting up TLS via ESSL...")
        from installer.utils import ensure_essl_installed, run_essl
        try:
            success, output = run_essl(domain, email, ESSL_CERT_DIR)
            if success:
                ok("TLS certificates generated.")
                # Point nginx at the certs
                from installer.utils import NGINX_CONF
                if NGINX_CONF.exists():
                    import re
                    content = NGINX_CONF.read_text()
                    content = re.sub(r"ssl_certificate .*;\n", "", content)
                    content = re.sub(r"ssl_certificate_key .*;\n", "", content)
                    ssl_block = f"""
    listen 443 ssl;
    ssl_certificate {ESSL_CERT_DIR / 'fullchain.pem'};
    ssl_certificate_key {ESSL_CERT_DIR / 'privkey.pem'};
    ssl_protocols TLSv1.2 TLSv1.3;
"""
                    content = content.replace("listen 80;", "listen 80;\n" + ssl_block, 1)
                    NGINX_CONF.write_text(content)
                    ok("Nginx configured for TLS.")
            else:
                warn("ESSL failed. Continuing without TLS.")
                print(dim(output))
        except Exception as e:
            warn(f"TLS setup failed: {e}. Continuing without TLS.")

    # 6. Pull and start containers
    info("Pulling and starting containers...")
    rc, out = docker_compose_pull(stream_output=True)
    if rc != 0:
        fail("docker compose pull failed")
        sys.exit(1)
    rc, out = docker_compose_up(stream_output=True)
    if rc != 0:
        fail("docker compose up failed")
        sys.exit(1)
    ok("Containers started successfully.")

    # 7. Ensure eovpanel CLI is in PATH
    venv_bin = str(REPO_ROOT / ".venv-installer" / "bin" / "eovpanel")
    target = "/usr/local/bin/eovpanel"
    if not shutil.which("eovpanel") or not os.path.islink(target):
        os.symlink(venv_bin, target)
        ok("eovpanel CLI added to /usr/local/bin/")

    # ── Done ───────────────────────────────────────────────────────────
    heading("Installation complete!")
    ip = public_ip or detect_public_ip() or "<your-server-ip>"
    panel_port = panel_port if panel_port != "80" else ""
    panel_url = f"http://{ip}:{panel_port}" if panel_port else f"http://{ip}"
    if panel_path:
        panel_url = f"{panel_url}/{panel_path}"
    print(f"""
  {bold('Panel URL:')}     {panel_url}
  {bold('Login:')}         {admin_user} / {'<password>' if admin_pass == args.admin_pass else '<password>'}
  {bold('OpenVPN CA:')}    {REPO_ROOT}/vpn-core/
  {bold('Backend .env:')}  {ENV_FILE}
  {bold('Docker Compose:')} {COMPOSE_FILE}

  {bold('Next steps:')}
    1. Open the panel URL in your browser
    2. Log in with your admin credentials
    3. {yellow('Change the default admin password immediately!')}
    4. Create your first VPN user from the Users page
    5. Download the .ovpn config and test connectivity

  {dim('To reconfigure, run: eovpanel configure')}
  {dim('To uninstall, run:   eovpanel uninstall')}
""")

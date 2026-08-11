"""
Application settings — loaded from .env (dev) or environment variables (prod).

Every setting has a sensible default so the app runs with zero configuration.
"""

from decouple import config

# --- App ---
APP_NAME: str = config("APP_NAME", default="eovpanel")
APP_VERSION: str = config("APP_VERSION", default="0.1.0")
DEBUG: bool = config("DEBUG", default=False, cast=bool)

# Optional base path the panel is served under (e.g. "/dashboard"), used to
# hide the panel from internet scanners. Empty = served at root. Subscription
# links and the landing page are prefixed with it so they keep working behind
# the nginx prefix-stripping proxy.
APP_BASE_PATH: str = config("APP_BASE_PATH", default="").strip().rstrip("/")
if APP_BASE_PATH and not APP_BASE_PATH.startswith("/"):
    APP_BASE_PATH = "/" + APP_BASE_PATH

# --- Server ---
HOST: str = config("HOST", default="0.0.0.0")
PORT: int = config("PORT", default=8000, cast=int)

# --- Database ---
DATABASE_URL: str = config(
    "DATABASE_URL",
    default="sqlite:///./eovpanel.db",
)

# --- JWT ---
JWT_SECRET_KEY: str = config("JWT_SECRET_KEY", default="changeme-in-production")
JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = config(
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", default=30, cast=int
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = config(
    "JWT_REFRESH_TOKEN_EXPIRE_DAYS", default=7, cast=int
)

# --- CORS ---
CORS_ORIGINS: list[str] = config(
    "CORS_ORIGINS",
    default="http://localhost:5173,http://localhost:3000",
    cast=lambda v: [s.strip() for s in v.split(",")],
)
CORS_ALLOW_CREDENTIALS: bool = config("CORS_ALLOW_CREDENTIALS", default=True, cast=bool)
CORS_ALLOW_METHODS: list[str] = config(
    "CORS_ALLOW_METHODS",
    default="*",
    cast=lambda v: [s.strip() for s in v.split(",")],
)
CORS_ALLOW_HEADERS: list[str] = config(
    "CORS_ALLOW_HEADERS",
    default="*",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

# --- OpenVPN ---
OPENVPN_MANAGEMENT_SOCKET: str = config(
    "OPENVPN_MANAGEMENT_SOCKET",
    default="/run/openvpn/management.sock",
)
OPENVPN_STATUS_LOG: str = config(
    "OPENVPN_STATUS_LOG",
    default="/opt/eovpanel/vpn/status.log",
)
EASYRSA_DIR: str = config(
    "EASYRSA_DIR",
    default="/opt/eovpanel/vpn/easy-rsa",
)

# --- Backups ---
# Directory where full-panel backup archives are stored.  Mounted read/write
# from the host in docker-compose so backups survive container recreation.
BACKUP_DIR: str = config("BACKUP_DIR", default="/opt/eovpanel/backups")

# --- Telegram Bot ---
TELEGRAM_ENABLED: bool = config("TELEGRAM_ENABLED", default=False, cast=bool)
TELEGRAM_BOT_TOKEN: str = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_ADMIN_CHAT_IDS: list[str] = config(
    "TELEGRAM_ADMIN_CHAT_IDS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

"""
Application settings — loaded from .env (dev) or environment variables (prod).

Every setting has a sensible default so the app runs with zero configuration.
"""

from decouple import config

# --- App ---
APP_NAME: str = config("APP_NAME", default="eovpanel")
APP_VERSION: str = config("APP_VERSION", default="0.1.0")
DEBUG: bool = config("DEBUG", default=False, cast=bool)

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
    default="/etc/openvpn/status.log",
)
EASYRSA_DIR: str = config(
    "EASYRSA_DIR",
    default="/etc/openvpn/easy-rsa",
)

# --- Telegram Bot (stub, not wired yet) ---
TELEGRAM_BOT_TOKEN: str = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_LOG_CHAT_ID: str = config("TELEGRAM_LOG_CHAT_ID", default="")

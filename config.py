import base64
import os
from datetime import timedelta


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _env_flag(name, default="false"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _database_url():
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        sqlite_path = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "instance", "crew.db"))
        return f"sqlite:///{sqlite_path.replace(os.sep, '/')}"
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://"):]
    return value


def _trusted_hosts():
    return [host.strip() for host in os.getenv("TRUSTED_HOSTS", "").split(",") if host.strip()] or None


class Config:
    CREW_ENV = os.getenv("CREW_ENV", "development").strip().lower()
    IS_PRODUCTION = CREW_ENV == "production"

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    CREW_INVITE_CODE = os.getenv("CREW_INVITE_CODE", "CREW-2026")
    CREW_ADMIN_PASSWORD = os.getenv("CREW_ADMIN_PASSWORD", "CREW-ADMIN-2026")
    CREW_ADMIN_TOTP_SECRET = os.getenv("CREW_ADMIN_TOTP_SECRET", "").strip().replace(" ", "")
    DATABASE_URL = _database_url()
    AUTO_DB_MIGRATE = _env_flag("AUTO_DB_MIGRATE", "false" if IS_PRODUCTION else "true")

    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
    PASSWORD_MAX_LENGTH = int(os.getenv("PASSWORD_MAX_LENGTH", "128"))
    ADMIN_SESSION_HOURS = int(os.getenv("ADMIN_SESSION_HOURS", "4"))

    LOGIN_RATE_LIMIT_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "10"))
    LOGIN_RATE_LIMIT_WINDOW = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW", "900"))
    AUTH_IP_RATE_LIMIT_ATTEMPTS = int(os.getenv("AUTH_IP_RATE_LIMIT_ATTEMPTS", "40"))
    AUTH_IP_RATE_LIMIT_WINDOW = int(os.getenv("AUTH_IP_RATE_LIMIT_WINDOW", "900"))
    RECOVERY_RATE_LIMIT_ATTEMPTS = int(os.getenv("RECOVERY_RATE_LIMIT_ATTEMPTS", "6"))
    RECOVERY_RATE_LIMIT_WINDOW = int(os.getenv("RECOVERY_RATE_LIMIT_WINDOW", "1800"))
    PROFILE_CREATE_RATE_LIMIT_ATTEMPTS = int(os.getenv("PROFILE_CREATE_RATE_LIMIT_ATTEMPTS", "8"))
    PROFILE_CREATE_RATE_LIMIT_WINDOW = int(os.getenv("PROFILE_CREATE_RATE_LIMIT_WINDOW", "3600"))
    ADMIN_RATE_LIMIT_ATTEMPTS = int(os.getenv("ADMIN_RATE_LIMIT_ATTEMPTS", "6"))
    ADMIN_RATE_LIMIT_WINDOW = int(os.getenv("ADMIN_RATE_LIMIT_WINDOW", "1800"))

    SESSION_COOKIE_NAME = "crew_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", "true" if IS_PRODUCTION else "false")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_HOURS", "12")))

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    PREFERRED_URL_SCHEME = "https" if IS_PRODUCTION else "http"
    TRUSTED_HOSTS = _trusted_hosts()

    @classmethod
    def validate(cls):
        if not cls.IS_PRODUCTION:
            return
        problems = []
        if cls.SECRET_KEY in {"", "dev-only-change-me"} or len(cls.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be a random value of at least 32 characters")
        if cls.CREW_INVITE_CODE in {"", "CREW-2026"}:
            problems.append("CREW_INVITE_CODE must be changed")
        if cls.CREW_ADMIN_PASSWORD in {"", "CREW-ADMIN-2026"} or len(cls.CREW_ADMIN_PASSWORD) < 16:
            problems.append("CREW_ADMIN_PASSWORD must be changed and at least 16 characters")
        if not cls.DATABASE_URL.startswith("postgresql+"):
            problems.append("DATABASE_URL must point to PostgreSQL in production")
        if not cls.TRUSTED_HOSTS:
            problems.append("TRUSTED_HOSTS must list the public CREW hostnames in production")
        if cls.PASSWORD_MIN_LENGTH < 12:
            problems.append("PASSWORD_MIN_LENGTH must be at least 12 in production")
        if cls.CREW_ADMIN_TOTP_SECRET:
            try:
                padded = cls.CREW_ADMIN_TOTP_SECRET + "=" * ((8 - len(cls.CREW_ADMIN_TOTP_SECRET) % 8) % 8)
                decoded = base64.b32decode(padded, casefold=True)
                if len(decoded) < 16:
                    raise ValueError("short TOTP secret")
            except Exception:
                problems.append("CREW_ADMIN_TOTP_SECRET must be a valid Base32 secret when configured")
        if problems:
            raise RuntimeError("Production configuration is incomplete: " + "; ".join(problems))

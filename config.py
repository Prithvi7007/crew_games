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
    # SQLAlchemy 2 prefers an explicit psycopg v3 driver.
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://"):]
    return value


class Config:
    CREW_ENV = os.getenv("CREW_ENV", "development").strip().lower()
    IS_PRODUCTION = CREW_ENV == "production"

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    CREW_INVITE_CODE = os.getenv("CREW_INVITE_CODE", "CREW-2026")
    CREW_ADMIN_PASSWORD = os.getenv("CREW_ADMIN_PASSWORD", "CREW-ADMIN-2026")
    DATABASE_URL = _database_url()
    AUTO_DB_MIGRATE = _env_flag("AUTO_DB_MIGRATE", "false" if IS_PRODUCTION else "true")

    SESSION_COOKIE_NAME = "crew_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", "true" if IS_PRODUCTION else "false")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_HOURS", "12")))

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    PREFERRED_URL_SCHEME = "https" if IS_PRODUCTION else "http"

    # Set to the public hostname in production, e.g. crew.example.com.
    TRUSTED_HOSTS = [host.strip() for host in os.getenv("TRUSTED_HOSTS", "").split(",") if host.strip()] or None

    @classmethod
    def validate(cls):
        if not cls.IS_PRODUCTION:
            return
        problems = []
        if cls.SECRET_KEY in {"", "dev-only-change-me"} or len(cls.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be a random value of at least 32 characters")
        if cls.CREW_INVITE_CODE in {"", "CREW-2026"}:
            problems.append("CREW_INVITE_CODE must be changed")
        if cls.CREW_ADMIN_PASSWORD in {"", "CREW-ADMIN-2026"} or len(cls.CREW_ADMIN_PASSWORD) < 14:
            problems.append("CREW_ADMIN_PASSWORD must be changed and at least 14 characters")
        if not cls.DATABASE_URL.startswith("postgresql+"):
            problems.append("DATABASE_URL must point to PostgreSQL in production")
        if problems:
            raise RuntimeError("Production configuration is incomplete: " + "; ".join(problems))

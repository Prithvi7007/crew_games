import os

import pytest

os.environ.setdefault("CREW_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-crew")
os.environ.setdefault("CREW_INVITE_CODE", "TEST-INVITE")
os.environ.setdefault("CREW_ADMIN_PASSWORD", "test-admin-password-long-enough")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from app import create_app
from config import Config


@pytest.fixture
def app(tmp_path):
    Config.CREW_ENV = "development"
    Config.IS_PRODUCTION = False
    Config.SECRET_KEY = "test-secret-key-that-is-long-enough-for-crew"
    Config.CREW_INVITE_CODE = "TEST-INVITE"
    Config.CREW_ADMIN_PASSWORD = "test-admin-password-long-enough"
    Config.CREW_ADMIN_TOTP_SECRET = ""
    Config.DATABASE_URL = f"sqlite:///{tmp_path / 'crew-test.db'}"
    Config.APP_VERSION = "12.0.0"
    Config.AUTO_DB_MIGRATE = True
    Config.SESSION_COOKIE_SECURE = False
    Config.TRUSTED_HOSTS = None
    Config.LOGIN_RATE_LIMIT_ATTEMPTS = 2
    Config.AUTH_IP_RATE_LIMIT_ATTEMPTS = 10
    Config.RECOVERY_RATE_LIMIT_ATTEMPTS = 2
    Config.PROFILE_CREATE_RATE_LIMIT_ATTEMPTS = 3
    Config.ADMIN_RATE_LIMIT_ATTEMPTS = 2
    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client, path="/login"):
    client.get(path)
    with client.session_transaction() as session:
        return session["csrf_token"]

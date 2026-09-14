from pathlib import Path

from werkzeug.security import generate_password_hash

from app.db import create_profile
from tests.conftest import csrf


def make_profile(app, username="Tester", password="correct horse battery staple"):
    with app.app_context():
        return create_profile(
            username,
            generate_password_hash(password),
            "⭐",
            generate_password_hash("ORBIT-NOVA-COMET-RIVER-ABCD"),
        )


def login(client, username="Tester", password="correct horse battery staple"):
    token = csrf(client)
    return client.post(
        "/login",
        data={"csrf_token": token, "username": username, "password": password},
        follow_redirects=False,
    )


def test_security_headers_include_csp(client):
    response = client.get("/login")
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self' 'nonce-" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"].startswith("no-store")


def test_login_rate_limit_blocks_repeated_failures(app, client):
    make_profile(app)
    for _ in range(2):
        token = csrf(client)
        response = client.post(
            "/login",
            data={"csrf_token": token, "username": "Tester", "password": "wrong password"},
        )
        assert response.status_code == 200
    token = csrf(client)
    response = client.post(
        "/login",
        data={"csrf_token": token, "username": "Tester", "password": "wrong password"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_password_change_revokes_other_sessions(app):
    make_profile(app)
    first = app.test_client()
    second = app.test_client()
    assert login(first).status_code == 302
    assert login(second).status_code == 302

    token = csrf(first, "/profile")
    response = first.post(
        "/profile/password",
        data={
            "csrf_token": token,
            "current_password": "correct horse battery staple",
            "new_password": "a newer and much stronger passphrase",
            "new_password_confirm": "a newer and much stronger passphrase",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert first.get("/profile").status_code == 200
    response = second.get("/profile", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_legacy_admin_boolean_session_is_rejected(client):
    client.get("/admin/login")
    with client.session_transaction() as session:
        session["crew_admin"] = True
        session["crew_admin_at"] = 9999999999
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_game_javascript_does_not_use_html_injection_primitives():
    static = Path(__file__).parents[1] / "app" / "static" / "js"
    for name in ["mystery.js", "trivia.js", "tick-tock.js", "leaderboard.js"]:
        text = (static / name).read_text()
        assert "innerHTML" not in text
        assert "insertAdjacentHTML" not in text
        assert "outerHTML" not in text


def test_cross_origin_state_change_is_rejected(client):
    token = csrf(client)
    response = client.post(
        "/login",
        data={"csrf_token": token, "username": "Nobody", "password": "anything"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 400


def test_profile_creation_enforces_passphrase_length(client):
    token = csrf(client, "/create-profile")
    response = client.post(
        "/create-profile",
        data={
            "csrf_token": token,
            "invite_code": "TEST-INVITE",
            "username": "NewPlayer",
            "avatar": "⭐",
            "password": "short-pass",
            "password_confirm": "short-pass",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"at least 12 characters" in response.data


def test_totp_rfc6238_vector():
    import base64
    from app.security import verify_totp
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert verify_totp(secret, "287082", now=59, window=0)
    assert not verify_totp(secret, "287083", now=59, window=0)

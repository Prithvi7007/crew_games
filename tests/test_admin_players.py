import re

from werkzeug.security import check_password_hash, generate_password_hash

from app.db import create_profile, get_profile_by_id


def _create_player(app, username="AdminManagedPlayer"):
    with app.app_context():
        profile = create_profile(
            username,
            generate_password_hash("correct horse battery staple"),
            "⭐",
            generate_password_hash("ORBIT-NOVA-COMET-RIVER-ABCD"),
        )
        return int(profile["id"])


def _admin_login(client):
    client.get("/admin/login")
    with client.session_transaction() as session:
        token = session["csrf_token"]
    response = client.post(
        "/admin/login",
        data={"csrf_token": token, "password": "test-admin-password-long-enough", "otp": ""},
    )
    assert response.status_code == 302
    return token


def test_admin_players_directory_lists_accounts(app):
    _create_player(app, "DirectoryPlayer")
    client = app.test_client()
    _admin_login(client)
    response = client.get("/admin/players")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Manage the CREW." in html
    assert "DirectoryPlayer" in html
    assert "Player accounts" in html


def test_admin_force_sign_out_increments_session_version(app):
    profile_id = _create_player(app, "SessionPlayer")
    client = app.test_client()
    token = _admin_login(client)
    with app.app_context():
        before = int(get_profile_by_id(profile_id)["session_version"])
    response = client.post(
        f"/admin/players/{profile_id}/force-sign-out",
        data={"csrf_token": token},
    )
    assert response.status_code == 302
    with app.app_context():
        after = int(get_profile_by_id(profile_id)["session_version"])
    assert after == before + 1


def test_admin_can_generate_one_time_password_and_recovery_code(app):
    profile_id = _create_player(app, "RecoveryPlayer")
    client = app.test_client()
    token = _admin_login(client)

    response = client.post(
        f"/admin/players/{profile_id}/reset-password",
        data={"csrf_token": token},
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    match = re.search(r'<code class="admin-secret-value">([^<]+)</code>', html)
    assert match
    temporary_password = match.group(1)
    with app.app_context():
        profile = get_profile_by_id(profile_id)
        assert check_password_hash(profile["password_hash"], temporary_password)

    response = client.post(
        f"/admin/players/{profile_id}/reset-recovery",
        data={"csrf_token": token},
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    match = re.search(r'<code class="admin-secret-value">([^<]+)</code>', html)
    assert match
    recovery_code = match.group(1)
    with app.app_context():
        profile = get_profile_by_id(profile_id)
        assert check_password_hash(profile["recovery_code_hash"], recovery_code.upper())

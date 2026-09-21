from werkzeug.security import generate_password_hash

from app.db import create_profile, get_profile_by_id, get_setting, profile_user_key


def _profile(app, username, role="player"):
    from app.db import update_profile_role
    with app.app_context():
        profile = create_profile(
            username,
            generate_password_hash("correct horse battery staple"),
            "⭐",
            generate_password_hash("ORBIT-NOVA-COMET-RIVER-ABCD"),
        )
        profile_id = int(profile["id"])
        if role != "player":
            update_profile_role(profile_id, role)
        return profile_id


def _sign_in(client, app, profile_id):
    with app.app_context():
        profile = get_profile_by_id(profile_id)
        user = {
            "profile_id": profile_id,
            "username": profile["username"],
            "avatar": profile["avatar"],
            "role": profile["role"],
            "user_key": profile_user_key(profile_id),
            "session_version": int(profile["session_version"]),
        }
    client.get("/login")
    with client.session_transaction() as session:
        session["user"] = user
        return session["csrf_token"]


def _breakglass(client):
    client.get("/admin/login")
    with client.session_transaction() as session:
        token = session["csrf_token"]
    response = client.post(
        "/admin/login",
        data={"csrf_token": token, "password": "test-admin-password-long-enough", "otp": ""},
    )
    assert response.status_code == 302
    return token


def test_admin_profile_can_open_admin_and_player_cannot(app):
    admin_id = _profile(app, "RoleAdmin", "admin")
    player_id = _profile(app, "RolePlayer")

    admin_client = app.test_client()
    _sign_in(admin_client, app, admin_id)
    assert admin_client.get("/admin").status_code == 200

    player_client = app.test_client()
    _sign_in(player_client, app, player_id)
    response = player_client.get("/admin")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/home")


def test_admin_can_promote_and_revoke_player(app):
    admin_id = _profile(app, "PromotingAdmin", "admin")
    target_id = _profile(app, "PromotionTarget")
    client = app.test_client()
    token = _sign_in(client, app, admin_id)

    response = client.post(
        f"/admin/players/{target_id}/role",
        data={"csrf_token": token, "role": "admin"},
    )
    assert response.status_code == 302
    with app.app_context():
        target = get_profile_by_id(target_id)
        assert target["role"] == "admin"
        promoted_version = int(target["session_version"])

    client.post(
        f"/admin/players/{target_id}/role",
        data={"csrf_token": token, "role": "player"},
    )
    with app.app_context():
        target = get_profile_by_id(target_id)
        assert target["role"] == "player"
        assert int(target["session_version"]) == promoted_version + 1


def test_admin_delete_requires_player_role(app):
    admin_id = _profile(app, "DeletingAdmin", "admin")
    player_id = _profile(app, "DeleteMe")
    other_admin_id = _profile(app, "ProtectedAdmin", "admin")
    client = app.test_client()
    token = _sign_in(client, app, admin_id)

    client.post(
        f"/admin/players/{other_admin_id}/delete",
        data={"csrf_token": token, "confirm_username": "ProtectedAdmin"},
    )
    with app.app_context():
        assert get_profile_by_id(other_admin_id) is not None

    client.post(
        f"/admin/players/{player_id}/delete",
        data={"csrf_token": token, "confirm_username": "DeleteMe"},
    )
    with app.app_context():
        assert get_profile_by_id(player_id) is None


def test_breakglass_can_assign_owner_but_admin_cannot(app):
    admin_id = _profile(app, "StandardAdmin", "admin")
    target_id = _profile(app, "FutureOwner")

    admin_client = app.test_client()
    admin_token = _sign_in(admin_client, app, admin_id)
    admin_client.post(
        f"/admin/players/{target_id}/role",
        data={"csrf_token": admin_token, "role": "owner"},
    )
    with app.app_context():
        assert get_profile_by_id(target_id)["role"] == "player"

    breakglass_client = app.test_client()
    breakglass_token = _breakglass(breakglass_client)
    breakglass_client.post(
        f"/admin/players/{target_id}/role",
        data={"csrf_token": breakglass_token, "role": "owner"},
    )
    with app.app_context():
        assert get_profile_by_id(target_id)["role"] == "owner"


def test_admin_can_change_invite_code_hash(app):
    admin_id = _profile(app, "SettingsAdmin", "admin")
    client = app.test_client()
    token = _sign_in(client, app, admin_id)
    response = client.post(
        "/admin/settings",
        data={
            "csrf_token": token,
            "invite_code": "NEW-CREW-CODE",
            "invite_code_confirm": "NEW-CREW-CODE",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        assert get_setting("invite_code_hash")


def test_admin_test_mode_future_games_do_not_create_attempts(app):
    admin_id = _profile(app, "TestingAdmin", "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)

    for game_key, day in (
        ("mystery", "2026-09-21"),
        ("trivia", "2026-09-22"),
        ("word", "2026-09-23"),
        ("tick_tock", "2026-09-24"),
    ):
        response = client.get(f"/admin/test/{game_key}/{day}")
        assert response.status_code == 200
        assert b"ADMIN TEST MODE" in response.data

    with app.app_context():
        from app.db import get_db
        for table in ("mystery_attempts", "trivia_attempts", "word_attempts", "tick_tock_attempts"):
            row = get_db().execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            assert int(row["count"]) == 0

def test_breakglass_can_override_signed_in_admin_without_player_signout(app):
    admin_id = _profile(app, "SignedInAdmin", "admin")
    target_id = _profile(app, "OwnerCandidate")
    client = app.test_client()
    token = _sign_in(client, app, admin_id)

    response = client.get("/admin/login?breakglass=1")
    assert response.status_code == 200

    response = client.post(
        "/admin/login?breakglass=1",
        data={
            "csrf_token": token,
            "password": "test-admin-password-long-enough",
            "otp": "",
        },
    )
    assert response.status_code == 302

    response = client.post(
        f"/admin/players/{target_id}/role",
        data={"csrf_token": token, "role": "owner"},
    )
    assert response.status_code == 302

    with app.app_context():
        assert get_profile_by_id(target_id)["role"] == "owner"


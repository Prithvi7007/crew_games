"""Cache-safe, staff-only stylesheet loading for Rewind Saga.

Rewind's React bundle was fingerprinted already, but the independent Saga
stylesheet could remain cached for 24 hours after its CSS changed.
"""
from datetime import date
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app.db import create_profile, get_profile_by_id, profile_user_key, update_profile_role
from app.player_ui import static_asset_version

ROOT = Path(__file__).resolve().parents[1]
SAGA_CSS = ROOT / "app/static/css/rewind-saga.css"


def test_saga_stylesheet_version_matches_actual_content():
    expected = sha256(SAGA_CSS.read_bytes()).hexdigest()[:12]
    assert expected != "missing"
    assert static_asset_version("css/rewind-saga.css") == expected


def test_saga_css_cache_busts_on_edit_without_requiring_js_bundle():
    from app import player_ui
    name = "css/rewind-saga.css"
    expected = sha256(SAGA_CSS.read_bytes()).hexdigest()[:12]
    assert static_asset_version(name) == expected
    with patch.object(player_ui, "_STATIC_ASSET_DIR") as fake_dir:
        # A missing stylesheet receives an explicit sentinel rather than a
        # stale static-asset fingerprint.
        fake_dir.__truediv__.return_value.stat.side_effect = OSError()
        assert static_asset_version(name) == "missing"


def test_saga_css_is_head_loaded_with_fingerprint_only_for_staff_preview(app, client):
    with app.app_context():
        admin = create_profile(
            "SagaCssAdmin", generate_password_hash("test-password"), "⭐",
            generate_password_hash("test-key"),
        )
        pid = int(admin["id"])
        update_profile_role(pid, "admin")
        p = get_profile_by_id(pid)
        user = {
            "profile_id": pid, "username": p["username"], "role": p["role"],
            "avatar": p["avatar"], "user_key": profile_user_key(pid),
            "session_version": int(p["session_version"]),
        }

    client.get("/login")
    with client.session_transaction() as session:
        session["user"] = user

    with patch("app.main.routes.crew_today", return_value=date(2026, 10, 26)):
        saga = client.get("/rewind?preview=1&prototype=1&story=5")
        assert saga.status_code == 200
        expected = static_asset_version("css/rewind-saga.css")
        assert (f'/static/css/rewind-saga.css?v={expected}').encode() in saga.data
        assert saga.headers["Cache-Control"] == "private, no-store"
        assert saga.data.index(b"rewind-saga.css?v=") < saga.data.index(b'id="crew-player-root"')

        cinema = client.get("/rewind?preview=1&prototype=1&story=4")
        assert cinema.status_code == 200
        assert b"rewind-saga.css?v=" not in cinema.data

        normal = client.get("/rewind")
        assert normal.status_code in (200, 404)  # No finalized public story yet.
        assert b"rewind-saga.css?v=" not in normal.data


def test_saga_stylesheet_is_served_with_current_spotlight_rules(client):
    response = client.get("/static/css/rewind-saga.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert b".saga-spotlight-picks" in response.data
    assert b".saga-spotlight-rail" in response.data
    assert b".saga-dna-focus-bar" in response.data

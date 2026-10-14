"""Admin-only cinematic badge unlock preview: no player-facing behavior or writes."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.db import create_profile, get_db, profile_user_key

ROOT = Path(__file__).resolve().parents[1]


def _sign_in(client, app, role="player"):
    client.get("/login")
    with app.app_context():
        user = create_profile(
            "Cinematic" + role.title(), "test-hash",
            "🏆", "recovery-hash",
        )
    with client.session_transaction() as sess:
        sess["user"] = {
            "profile_id": int(user["id"]),
            "username": user["username"],
            "avatar": user["avatar"],
            "role": role,
            "user_key": profile_user_key(int(user["id"])),
            "session_version": int(user["session_version"] or 1),
        }


def _state(response):
    match = re.search(
        r'<script[^>]*id="player-state"[^>]*>(.*?)</script>',
        response.get_data(as_text=True), re.DOTALL,
    )
    assert match, "The player shell must render its JSON state"
    return json.loads(match.group(1))


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_only_staff_can_open_cinematic_preview_during_launch_hold(client, app, monkeypatch, role):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 14))
    _sign_in(client, app, role)
    normal = _state(client.get("/trophies"))
    preview_response = client.get("/trophies?unlock_preview=1")
    assert preview_response.status_code == 200
    preview = _state(preview_response)
    assert "unlockPreviewEnabled" in preview
    assert normal["unlockPreviewEnabled"] is False
    assert preview["unlockPreviewEnabled"] is True
    assert preview["trophyPreview"]["enabled"] is True
    assert preview["earnedCount"] == normal["earnedCount"]
    assert preview["showcase"] == normal["showcase"]


def test_player_cannot_open_trophy_preview_while_launch_is_held(client, app, monkeypatch):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 14))
    _sign_in(client, app)
    assert client.get("/trophies?unlock_preview=1").status_code == 404


def test_player_query_cannot_enable_cinematic_preview_after_launch(client, app, monkeypatch):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 19))
    _sign_in(client, app)
    response = client.get("/trophies?unlock_preview=1")
    assert response.status_code == 200
    state = _state(response)
    assert state["unlockPreviewEnabled"] is False
    assert state["trophyPreview"]["enabled"] is False


@pytest.mark.parametrize("suffix", ["", "?unlock_preview=0", "?unlock_preview=true", "?unlock_preview=1x"])
def test_staff_preview_requires_explicit_opt_in(client, app, monkeypatch, suffix):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 14))
    _sign_in(client, app, "admin")
    assert _state(client.get("/trophies" + suffix))["unlockPreviewEnabled"] is False


def test_preview_is_read_only_for_badges_games_and_tour(client, app, monkeypatch):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 14))
    _sign_in(client, app, "owner")

    def snapshot():
        with app.app_context():
            db = get_db()
            return (
                db.execute("SELECT COUNT(*) AS total FROM badge_awards").fetchone()["total"],
                db.execute("SELECT COUNT(*) AS total FROM badge_showcase").fetchone()["total"],
                db.execute("SELECT COUNT(*) AS total FROM game_completions").fetchone()["total"],
                db.execute("SELECT COUNT(*) AS total FROM trophy_tour_completions").fetchone()["total"],
            )

    before = snapshot()
    response = client.get("/trophies?unlock_preview=1")
    assert response.status_code == 200
    assert _state(response)["unlockPreviewEnabled"] is True
    assert snapshot() == before


def test_preview_components_do_not_call_game_or_badge_mutation_apis():
    frontend = ROOT / "frontend" / "src" / "player"
    preview = (frontend / "BadgeUnlockPreview.jsx").read_text(encoding="utf-8")
    entry = (frontend / "main.jsx").read_text(encoding="utf-8")
    route = (ROOT / "app" / "main" / "routes.py").read_text(encoding="utf-8")
    assert "BadgeMedallion" in preview
    assert "badgeFromAwardCode" in preview
    assert "postJson(" not in preview
    assert "fetch(" not in preview
    assert "awardId" not in preview
    assert "data.unlockPreviewEnabled && data.trophyPreview?.enabled" in entry
    assert 'preview_enabled and request.args.get("unlock_preview") == "1"' in route

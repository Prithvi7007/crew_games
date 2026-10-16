"""Launch-safe cross-game layout preview and completion-viewport contracts."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.db import create_profile, get_db, profile_user_key

ROOT = Path(__file__).resolve().parents[1]
GAME_URLS = (
    "/mystery?date=2026-10-12",
    "/trivia?date=2026-10-13",
    "/word?date=2026-10-14",
    "/tick-tock?date=2026-10-08",
)


def _signin(client, app, role):
    client.get("/login")
    with app.app_context():
        user = create_profile("GameplayPreview" + role.title(), "hash", "🎮", "recovery-hash")
    with client.session_transaction() as sess:
        sess["user"] = {
            "profile_id": int(user["id"]),
            "username": user["username"],
            "avatar": user["avatar"],
            "role": role,
            "user_key": profile_user_key(int(user["id"])),
            "session_version": int(user["session_version"] or 1),
        }


def _shell(client, url):
    response = client.get(url)
    assert response.status_code == 200, (url, response.status_code)
    match = re.search(
        r'<script[^>]*id="player-state"[^>]*>(.*?)</script>',
        response.get_data(as_text=True),
        re.DOTALL,
    )
    assert match
    return json.loads(match.group(1))["shell"]


@pytest.mark.parametrize("role", ("admin", "owner"))
@pytest.mark.parametrize("game_url", GAME_URLS)
def test_staff_preview_available_on_all_four_games(client, app, monkeypatch, role, game_url):
    monkeypatch.setattr("app.schedule.crew_today", lambda: date(2026, 10, 14))
    _signin(client, app, role)
    assert _shell(client, game_url + "&gameplay_preview=1")["gameplayPreviewEnabled"] is True
    assert _shell(client, game_url)["gameplayPreviewEnabled"] is False


@pytest.mark.parametrize("game_url", GAME_URLS)
def test_regular_player_cannot_force_gameplay_preview(client, app, monkeypatch, game_url):
    monkeypatch.setattr("app.schedule.crew_today", lambda: date(2026, 10, 14))
    _signin(client, app, "player")
    assert _shell(client, game_url + "&gameplay_preview=1")["gameplayPreviewEnabled"] is False


@pytest.mark.parametrize("query", ["", "?gameplay_preview=0", "?gameplay_preview=true", "?gameplay_preview=1x"])
def test_staff_requires_explicit_gameplay_preview_optin(client, app, query):
    _signin(client, app, "owner")
    assert _shell(client, "/home" + query)["gameplayPreviewEnabled"] is False


def test_gameplay_preview_never_creates_scores_or_badge_awards(client, app):
    _signin(client, app, "owner")
    def snapshot():
        with app.app_context():
            db = get_db()
            return (
                db.execute("SELECT COUNT(*) AS total FROM badge_awards").fetchone()["total"],
                db.execute("SELECT COUNT(*) AS total FROM game_completions").fetchone()["total"],
            )
    before = snapshot()
    _shell(client, "/word?date=2026-10-14&gameplay_preview=1")
    assert snapshot() == before


def test_preview_css_is_isolated_to_staff_body_class():
    css = (ROOT / "frontend/src/player/styles/gameplay-refinement.css").read_text(encoding="utf-8")
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    server = (ROOT / "app/player_ui.py").read_text(encoding="utf-8")
    assert "trophy_preview_enabled(user)" in server
    assert 'request.args.get("gameplay_preview") == "1"' in server
    assert 'page in {"mystery", "trivia", "word", "tick_tock"}' in server
    assert "classList.toggle('crew-gameplay-preview', data.shell?.gameplayPreviewEnabled === true)" in source
    assert "import './styles/gameplay-refinement.css'" in source
    assert "body.crew-gameplay-preview" in css
    assert "body.crew-gameplay-preview.mystery-page" in css
    assert "body.crew-gameplay-preview.v19-trivia-page" in css
    assert "body.crew-gameplay-preview.word-page" in css
    assert "body.crew-gameplay-preview.timer-page" in css
    assert "@media(max-width:680px)" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion:reduce" in css


def test_results_recenter_and_cinematic_reveal_is_separate_overlay():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    result_css = (ROOT / "frontend/src/player/styles/results.css").read_text(encoding="utf-8")
    cinema_css = (ROOT / "frontend/src/player/styles/badge-unlock-preview.css").read_text(encoding="utf-8")
    assert "function useCompletionViewport(completed)" in source
    assert "window.scrollTo(0, 0)" in source
    assert source.count("useCompletionViewport(state.completed)") == 4
    assert 'className="crew-result-presentation"' in source
    assert 'className="v19-trivia-main crew-result-presentation"' in source
    # Results stay independently positioned behind the portal; no inline card.
    assert "crew-result-presentation" in result_css
    assert "crew-badge-celebration" not in result_css
    assert "document.body," in source
    assert ".cul-cinema.cul-live" in cinema_css

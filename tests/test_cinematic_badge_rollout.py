"""Cinematic reward rollout must stay off until explicitly approved."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.db import create_profile, profile_user_key

ROOT = Path(__file__).resolve().parents[1]


def _signin(client, app, role):
    client.get("/login")
    with app.app_context():
        user = create_profile("CinemaRollout" + role.title(), "test-hash", "🏆", "recovery-hash")
    with client.session_transaction() as sess:
        sess["user"] = {
            "profile_id": int(user["id"]), "username": user["username"],
            "avatar": user["avatar"], "role": role,
            "user_key": profile_user_key(int(user["id"])),
            "session_version": int(user["session_version"] or 1),
        }


def _shell(client, response_url="/home"):
    response = client.get(response_url)
    assert response.status_code == 200
    match = re.search(
        r'<script[^>]*id="player-state"[^>]*>(.*?)</script>',
        response.get_data(as_text=True), re.DOTALL,
    )
    assert match
    return json.loads(match.group(1))["shell"]


@pytest.mark.parametrize("role", ["player", "admin", "owner"])
def test_public_cinematic_defaults_off(app, client, monkeypatch, role):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 19))
    app.config["CINEMATIC_BADGE_UNLOCKS_ENABLED"] = False
    _signin(client, app, role)
    shell = _shell(client)
    assert shell["cinematicBadgeUnlocksEnabled"] is False


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_staff_can_opt_into_real_unlock_test_while_public_rollout_off(app, client, monkeypatch, role):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 14))
    app.config["CINEMATIC_BADGE_UNLOCKS_ENABLED"] = False
    _signin(client, app, role)
    assert _shell(client, "/home?cinematic_unlock_test=1")["cinematicBadgeUnlocksEnabled"] is True
    assert _shell(client, "/home?cinematic_unlock_test=0")["cinematicBadgeUnlocksEnabled"] is False
    assert _shell(client, "/home")["cinematicBadgeUnlocksEnabled"] is False


@pytest.mark.parametrize("day,expected", [
    (date(2026, 10, 14), False),
    (date(2026, 10, 18), False),
    (date(2026, 10, 19), True),
    (date(2026, 10, 20), True),
])
def test_public_flag_still_obeys_october_19_hold(app, client, monkeypatch, day, expected):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: day)
    app.config["CINEMATIC_BADGE_UNLOCKS_ENABLED"] = True
    _signin(client, app, "player")
    assert _shell(client, "/home?cinematic_unlock_test=1")["cinematicBadgeUnlocksEnabled"] is expected


def test_regular_player_cannot_force_cinematic_with_query_when_flag_off(app, client, monkeypatch):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 19))
    app.config["CINEMATIC_BADGE_UNLOCKS_ENABLED"] = False
    _signin(client, app, "player")
    assert _shell(client, "/home?cinematic_unlock_test=1")["cinematicBadgeUnlocksEnabled"] is False


def test_real_unlock_consumes_only_saved_server_response_and_retains_fallback():
    src = (ROOT / "frontend/src/player" / "main.jsx").read_text(encoding="utf-8")
    cinematic = (ROOT / "frontend/src/player" / "BadgeUnlockPreview.jsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend/src/player" / "styles" / "badge-unlock-preview.css").read_text(encoding="utf-8")
    shell = (ROOT / "app" / "player_ui.py").read_text(encoding="utf-8")
    config = (ROOT / "config.py").read_text(encoding="utf-8")
    assert '_env_flag("CINEMATIC_BADGE_UNLOCKS_ENABLED", "false")' in config
    assert 'trophies_visible_to(user) and (' in shell
    assert 'trophy_preview_enabled(user)' in shell
    assert 'if (cinematic) return createPortal(' in src
    assert 'codes: medals.map(badge => badge.code)' in src
    assert 'const medals = [...new Set(codes)].map(badgeFromAwardCode).filter(Boolean);' in src
    assert 'if (!medals.length || dismissed) return null;' in src
    assert 'if(p.completed)setBadgesEarned(p.badge_awards||[]);' in src
    assert 'setBadgesEarned(p.badge_awards||[]);' in src
    assert 'showBadges ? <BadgeUnlockCelebration codes={badges} cinematic={cinematic} gameKey={game}/>' in src
    assert 'gameKey="trivia"' in src
    assert src.count('cinematic={data.shell?.cinematicBadgeUnlocksEnabled === true}') == 4
    assert 'export function CinematicReveal' in cinematic
    assert 'featured = badges.length <= 3 ? badges' in cinematic
    assert 'badges.map(badge => <div key={badge.code}' in cinematic
    assert 'onDismiss || skip' in cinematic
    assert 'prefers-reduced-motion: reduce' in cinematic or 'prefers-reduced-motion:reduce' in css
    assert 'cul-live' in css
    assert "postJson(" not in cinematic and "fetch(" not in cinematic


def test_previously_completed_page_does_not_supply_old_badge_awards():
    src = (ROOT / "frontend/src/player" / "main.jsx").read_text(encoding="utf-8")
    assert src.count("useState([])") >= 4
    assert 'if (!medals.length || dismissed) return null;' in src
    assert "badges={badgesEarned}" in src

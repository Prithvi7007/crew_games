"""The sole live achievement transition is the October 19-gated cinematic.

Admin's simulation lab is independent; no old inline result card or secondary
environment flag can silently select an unintended reveal.
"""

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


@pytest.mark.parametrize("day,expected", [
    (date(2026, 10, 14), False),
    (date(2026, 10, 18), False),
    (date(2026, 10, 19), True),
    (date(2026, 10, 20), True),
])
def test_public_badge_reveal_follows_launch_date(app, client, monkeypatch, day, expected):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: day)
    _signin(client, app, "player")
    shell = _shell(client, "/home?cinematic_unlock_test=1")
    assert shell["trophiesVisible"] is expected
    assert "cinematicBadgeUnlocksEnabled" not in shell


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_staff_access_to_badges_not_blocked_by_public_reveal(app, client, monkeypatch, role):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 14))
    _signin(client, app, role)
    shell = _shell(client)
    assert shell["trophiesVisible"] is True
    assert "cinematicBadgeUnlocksEnabled" not in shell


def test_cinematic_is_only_game_unlock_renderer():
    src = (ROOT / "frontend/src/player" / "main.jsx").read_text(encoding="utf-8")
    cinematic = (ROOT / "frontend/src/player" / "BadgeUnlockPreview.jsx").read_text(encoding="utf-8")
    result_css = (ROOT / "frontend/src/player/styles/results.css").read_text(encoding="utf-8")
    trophy_css = (ROOT / "frontend/src/player/styles/trophies.css").read_text(encoding="utf-8")
    shell = (ROOT / "app/player_ui.py").read_text(encoding="utf-8")
    config = (ROOT / "config.py").read_text(encoding="utf-8")

    # A single server-confirmed reveal component works for all four games.
    assert "function BadgeUnlockCelebration({ codes=[], gameKey=null })" in src
    assert "const medals = [...new Set(codes)].map(badgeFromAwardCode).filter(Boolean);" in src
    assert "if (!medals.length || dismissed) return null;" in src
    assert "return createPortal(" in src
    assert "<CinematicReveal preset={{ codes: medals.map(badge => badge.code) }}" in src
    assert "if(p.completed)setBadgesEarned(p.badge_awards||[]);" in src
    assert "setBadgesEarned(p.badge_awards||[]);" in src
    assert src.count("<BadgeUnlockCelebration codes={") == 2  # shared result + Trivia
    assert src.count("showBadges={data.shell?.trophiesVisible !== false}") == 3
    assert 'codes={badgesEarned} gameKey="trivia"' in src

    # No old presentation or alternate setting remains.
    assert "crew-badge-celebration" not in src + result_css + trophy_css
    assert "crew-badge-reveal" not in src + result_css + trophy_css
    assert "cinematicBadgeUnlocksEnabled" not in src + shell
    assert "CINEMATIC_BADGE_UNLOCKS_ENABLED" not in config
    assert "cinematic_unlock_test" not in shell
    assert "export function CinematicReveal" in cinematic
    assert "onDismiss || skip" in cinematic
    assert "prefers-reduced-motion:reduce" in cinematic or "prefers-reduced-motion:reduce" in (
        ROOT / "frontend/src/player/styles/badge-unlock-preview.css"
    ).read_text(encoding="utf-8")


def test_reopening_completed_result_cannot_replay_old_unlock():
    src = (ROOT / "frontend/src/player" / "main.jsx").read_text(encoding="utf-8")
    assert src.count("useState([])") >= 4
    assert "if (!medals.length || dismissed) return null;" in src
    assert "badges={badgesEarned}" in src

"""Trophy launch hold and Rankings color system regression coverage."""
from datetime import date
from pathlib import Path

import pytest

from app.db import create_profile, profile_user_key
from app.trophy_access import TROPHY_PUBLIC_REVEAL_DATE, trophies_visible_to

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("day,expected", [
    (date(2026, 10, 11), False),
    (date(2026, 10, 12), False),
    (date(2026, 10, 18), False),
    (date(2026, 10, 19), True),
    (date(2026, 10, 20), True),
])
def test_player_trophies_reopen_monday_october_19(day, expected):
    assert TROPHY_PUBLIC_REVEAL_DATE == date(2026, 10, 19)
    assert trophies_visible_to({"role": "player"}, today=day) is expected


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_staff_can_preview_collection_during_hold(role):
    assert trophies_visible_to({"role": role}, today=date(2026, 10, 12))


def _sign_in_test_player(client, app, role="player"):
    client.get("/login")
    with app.app_context():
        profile = create_profile("TrophyHoldTest", "test-hash", "🎬", "recovery-hash")
        profile_id = int(profile["id"])
        session_version = int(profile["session_version"] or 1)

    with client.session_transaction() as sess:
        sess["user"] = {
            "profile_id": profile_id,
            "username": "TrophyHoldTest",
            "avatar": "🎬",
            "role": role,
            "user_key": profile_user_key(profile_id),
            "session_version": session_version,
        }
        csrf_token = sess["csrf_token"]
    return csrf_token


def test_player_route_and_badge_write_are_closed_but_rankings_work(client, app, monkeypatch):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 12))
    token = _sign_in_test_player(client, app)
    assert client.get("/trophies").status_code == 404
    assert client.get("/trophies?season=1").status_code == 404
    response = client.post(
        "/api/trophies/showcase",
        json={"slot": 1, "awardId": None},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 404
    rankings = client.get("/leaderboard")
    assert rankings.status_code == 200
    assert b'"trophiesVisible": false' in rankings.data
    profile = client.get("/profile")
    assert profile.status_code == 200
    assert b'"trophiesVisible": false' in profile.data


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_staff_routes_can_preview_before_public_open(client, app, monkeypatch, role):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 12))
    token = _sign_in_test_player(client, app, role=role)
    response = client.get("/trophies")
    assert response.status_code == 200
    assert b'"trophiesVisible": true' in response.data
    # An invalid payload should be validated normally rather than held at 404.
    response = client.post("/api/trophies/showcase", json={}, headers={"X-CSRFToken": token})
    assert response.status_code == 400


def test_trophy_room_opens_automatically_for_player(client, app, monkeypatch):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 19))
    _sign_in_test_player(client, app)
    response = client.get("/trophies")
    assert response.status_code == 200
    assert b'"trophiesVisible": true' in response.data


def test_hidden_nav_and_cinematic_reveal_share_launch_gate():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    assert 'trophiesVisible ? link(\'trophies\'' in source
    assert "trophiesVisible={trophiesVisible}" in source
    assert "showBadges ? <BadgeUnlockCelebration codes={badges} gameKey={game}/> : null" in source
    assert source.count("showBadges={data.shell?.trophiesVisible !== false}") == 3
    assert 'data.shell?.trophiesVisible !== false ? <BadgeUnlockCelebration codes={badgesEarned} gameKey="trivia"/>' in source
    assert "cinematicBadgeUnlocksEnabled" not in source


def test_rankings_tabs_match_crew_game_palette():
    jsx = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend/src/player/styles/rankings.css").read_text(encoding="utf-8")
    assert "data-game={value}" in jsx
    for game, color in (
        ("mystery", "#55e6ac"),
        ("trivia", "#ffbd45"),
        ("word", "#55b9ff"),
        ("tick_tock", "#c55cff"),
    ):
        assert f'button[data-game="{game}"] {{--rankings-tab-accent:{color};}}' in css
    assert "--rankings-tab-accent:#35dff9;" in css
    assert "border-color:var(--rankings-tab-accent)" in css

"""Trophy Room: authenticated, season-specific, server-owned award data."""

import json
import re
from datetime import date

from werkzeug.security import generate_password_hash

from app.badge_store import award_badges, get_badge_awards, set_showcase_slot
from app.db import create_profile, get_profile_by_id, get_season_for_date, profile_user_key


def _profile(app, name):
    with app.app_context():
        user = create_profile(
            name, generate_password_hash("trophy-password-example"),
            "🏆", generate_password_hash("trophy-recovery-example"),
        )
        return int(user["id"])


def _signin(client, app, profile_id):
    with app.app_context():
        profile = get_profile_by_id(profile_id)
        user = {
            "profile_id": profile_id, "username": profile["username"],
            "avatar": profile["avatar"], "role": profile["role"],
            "user_key": profile_user_key(profile_id),
            "session_version": int(profile["session_version"]),
        }
    client.get("/login")
    with client.session_transaction() as session:
        session["user"] = user


def _payload(response):
    html = response.get_data(as_text=True)
    match = re.search(
        r'<script[^>]*id="player-state"[^>]*>(.*?)</script>',
        html, flags=re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_trophy_room_requires_login(client):
    response = client.get("/trophies")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_trophy_room_shows_all_21_catalog_entries_without_fake_awards(app, client):
    owner = _profile(app, "TrophyZero")
    _signin(client, app, owner)
    response = client.get("/trophies")
    assert response.status_code == 200
    data = _payload(response)
    assert len(data["badges"]) == 21
    assert data["earnedCount"] == 0
    assert data["showcase"] == []
    assert all(not badge["earned"] for badge in data["badges"])
    assert data["selectedSeason"]["number"] == 1
    assert response.headers.get("Content-Security-Policy") is not None


def test_trophy_room_never_exposes_another_players_awards(app, client):
    owner = _profile(app, "TrophyOwner")
    other = _profile(app, "TrophyOther")
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 7))
        award_badges(owner, season["id"], ("word_wizard",), source_date="2026-10-07")
        award_badges(other, season["id"], ("unicorn",), source_date="2026-10-07")
        owner_awards = get_badge_awards(owner, season["id"])
        set_showcase_slot(owner, 1, owner_awards[0]["id"])
    _signin(client, app, owner)
    data = _payload(client.get("/trophies"))
    assert data["earnedCount"] == 1
    assert {badge["code"] for badge in data["badges"] if badge["earned"]} == {"word_wizard"}
    assert data["showcase"] == [{"slot": 1, "badgeCode": "word_wizard"}]


def test_trophy_room_invalid_season_falls_back_to_current(app, client):
    owner = _profile(app, "TrophyFilter")
    _signin(client, app, owner)
    data = _payload(client.get("/trophies?season=999999"))
    assert data["selectedSeason"]["number"] == 1
    assert data["earnedCount"] == 0

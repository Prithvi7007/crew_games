"""Trophy Room: authenticated, season-specific, server-owned award data."""

import json
import re
from datetime import date

import pytest


@pytest.fixture(autouse=True)
def collection_contract_after_public_reveal(monkeypatch):
    """These existing collection contracts apply once public access reopens."""
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 19))

from werkzeug.security import generate_password_hash

from app.badge_store import award_badges, get_badge_awards, set_showcase_slot
from app.db import create_profile, create_season, get_profile_by_id, get_season_for_date, profile_user_key


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
    assert len(data["showcase"]) == 1
    assert data["showcase"][0]["slot"] == 1
    assert data["showcase"][0]["badgeCode"] == "word_wizard"
    assert data["showcase"][0]["awardId"] == owner_awards[0]["id"]


def test_trophy_room_invalid_season_falls_back_to_current(app, client):
    owner = _profile(app, "TrophyFilter")
    _signin(client, app, owner)
    data = _payload(client.get("/trophies?season=999999"))
    assert data["selectedSeason"]["number"] == 1
    assert data["earnedCount"] == 0


def test_prior_season_badge_can_be_worn_while_viewing_current_collection(app, client, monkeypatch):
    today = date(2026, 11, 2)
    monkeypatch.setattr("app.main.routes.crew_today", lambda: today)
    monkeypatch.setattr("app.schedule.crew_today", lambda: today)
    owner = _profile(app, "SeasonBadgeOwner")
    with app.app_context():
        first = get_season_for_date(date(2026, 10, 12))
        second = get_season_for_date(today) or create_season("Season 2", today, date(2026, 12, 13))
        award_badges(owner, first["id"], ("case_closed",), source_date="2026-10-12")
        award_badges(owner, second["id"], ("case_closed",), source_date="2026-11-02")
        old_award = int(get_badge_awards(owner, first["id"])[0]["id"])
        new_award = int(get_badge_awards(owner, second["id"])[0]["id"])
    _signin(client, app, owner)
    current = _payload(client.get("/trophies"))
    assert current["selectedSeason"]["id"] == second["id"]
    assert {season["id"] for season in current["seasons"]} >= {first["id"], second["id"]}
    historical = _payload(client.get(f'/trophies?season={first["id"]}'))
    assert historical["selectedSeason"]["id"] == first["id"]
    assert historical["earnedCount"] == current["earnedCount"] == 1
    assert next(b["awardId"] for b in historical["badges"] if b["earned"]) == old_award
    assert next(b["awardId"] for b in current["badges"] if b["earned"]) == new_award
    assert old_award != new_award
    with client.session_transaction() as session:
        token = session["csrf_token"]
    saved = client.post("/api/trophies/showcase", json={"slot": 1, "awardId": old_award},
                        headers={"X-CSRFToken": token})
    assert saved.status_code == 200
    assert saved.json["showcase"][0]["badge"]["seasonNumber"] == 1
    for url, season_id in (("/trophies", second["id"]), (f'/trophies?season={first["id"]}', first["id"])):
        data = _payload(client.get(url))
        assert data["selectedSeason"]["id"] == season_id
        assert data["showcase"][0]["awardId"] == old_award
        assert data["shell"]["userEquippedBadge"]["seasonNumber"] == 1
    assert _payload(client.get("/profile"))["equippedBadge"]["seasonNumber"] == 1


def test_showcase_api_rejects_anonymous_and_missing_csrf(app, client):
    assert client.post("/api/trophies/showcase", json={"slot": 1, "awardId": None}).status_code == 400
    client.get("/login")
    with client.session_transaction() as session:
        csrf = session["csrf_token"]
    assert client.post(
        "/api/trophies/showcase", json={"slot": 1, "awardId": None},
        headers={"X-CSRFToken": csrf},
    ).status_code == 302
    owner = _profile(app, "ShowcaseCsrf")
    _signin(client, app, owner)
    assert client.post("/api/trophies/showcase", json={"slot": 1, "awardId": None}).status_code == 400


def test_showcase_api_limits_edits_to_own_badges_and_three_slots(app, client):
    owner = _profile(app, "ShowcaseOwner")
    other = _profile(app, "ShowcaseOther")
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 7))
        award_badges(owner, season["id"], ("brainiac", "word_wizard"), source_date="2026-10-07")
        award_badges(other, season["id"], ("unicorn",), source_date="2026-10-07")
        owned = {row["badge_code"]: row["id"] for row in get_badge_awards(owner, season["id"])}
        foreign = get_badge_awards(other, season["id"])[0]["id"]
    _signin(client, app, owner)
    with client.session_transaction() as session:
        token = session["csrf_token"]
    headers = {"X-CSRFToken": token}

    def send(slot, award_id):
        return client.post(
            "/api/trophies/showcase", json={"slot": slot, "awardId": award_id},
            headers=headers,
        )

    assert send(1, foreign).status_code == 400
    assert send(4, owned["brainiac"]).status_code == 400
    assert send(True, owned["brainiac"]).status_code == 400
    assert send(1, "1").status_code == 400
    assert send(1, owned["brainiac"]).status_code == 200
    assert send(2, owned["brainiac"]).status_code == 400
    response = send(2, owned["word_wizard"])
    assert response.status_code == 200
    assert {item["badgeCode"] for item in response.json["showcase"]} == {"brainiac", "word_wizard"}
    assert send(1, None).status_code == 200
    assert [item["slot"] for item in send(2, owned["word_wizard"]).json["showcase"]] == [2]


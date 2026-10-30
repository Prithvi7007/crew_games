"""Staff-only champion animation demos must never create real awards."""
import json
import re
from datetime import date
from unittest.mock import patch

import pytest
from werkzeug.security import generate_password_hash

from app.championships import finalize_season_championships
from app.db import (
    create_profile, finalize_game_stats, get_db, get_profile_by_id,
    get_season_for_date, profile_user_key, update_profile_role,
)

BASE = "/rewind?preview=1&prototype=1&story=5"
CODES = {
    "season": "season_champion",
    "trivia": "season_trivia_master",
    "word": "season_wordle_master",
    "mystery": "season_mystery_master",
    "tick_tock": "season_tick_tock_master",
}


def player(name, role="player"):
    p = create_profile(name, generate_password_hash("test-password"), "⭐",
                       generate_password_hash("test-key"))
    pid = int(p["id"])
    if role != "player":
        update_profile_role(pid, role)
    return pid


def login(client, pid):
    p = get_profile_by_id(pid)
    client.get("/login")
    with client.session_transaction() as sess:
        sess["user"] = {
            "profile_id": pid, "username": p["username"], "role": p["role"],
            "avatar": p["avatar"], "user_key": profile_user_key(pid),
            "session_version": int(p["session_version"]),
        }


def state(response):
    assert response.status_code == 200
    match = re.search(
        rb'<script[^>]+id="player-state"[^>]*>(.*?)</script>',
        response.data, re.S,
    )
    assert match is not None
    return json.loads(match.group(1))


def competition_state():
    db = get_db()
    return {
        table: [dict(row) for row in db.execute("SELECT * FROM " + table).fetchall()]
        for table in ("game_completions", "badge_awards", "season_badge_finalizations")
    }


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_all_champion_demo_preserves_real_results_and_database(app, client, role):
    with app.app_context():
        pid = player("ChampionPreviewStaff", role)
        other = player("ChampionPreviewOther")
        finalize_game_stats(profile_user_key(other), "trivia", "2026-10-20", 90, True)
        login(client, pid)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 30)):
            original = state(client.get(BASE))
            before = competition_state()
            response = client.get(BASE + "&champion=all")
            demo = state(response)
            assert response.headers["Cache-Control"] == "private, no-store"
            assert demo["rewindChampionPreview"]["selection"] == "all"
            assert {o["key"] for o in demo["rewindChampionPreview"]["options"]} == {
                "all", *CODES,
            }
            saga = demo["rewind"]["seasonSaga"]
            assert saga["demo"] is True
            assert [b["kind"] for b in saga["beats"]] == ["winner", "winner_badge"] * 5
            assert [b["visual"]["badge"]["code"] for b in saga["beats"]
                    if b["kind"] == "winner_badge"] == list(CODES.values())
            assert saga["count"] == 10
            assert demo["rewind"]["champion"] is False
            assert demo["rewind"]["finalized"] is False
            assert {k: v for k, v in demo["rewind"].items() if k != "seasonSaga"} == {
                k: v for k, v in original["rewind"].items() if k != "seasonSaga"
            }
            assert competition_state() == before

            # Staff may use the same demo while viewing another player's real data.
            cross = state(client.get(BASE + "&champion=all&player=ChampionPreviewOther"))
            assert cross["rewind"]["username"] == "ChampionPreviewOther"
            assert cross["rewind"]["points"] == 90
            assert cross["rewind"]["champion"] is False
            assert cross["rewind"]["badges"]["count"] == 0
            assert competition_state() == before

            # Leaving the demo must return the unmodified actual story.
            normal = state(client.get(BASE))
            assert normal.get("rewindChampionPreview") is None
            assert normal["rewind"]["seasonSaga"] == original["rewind"]["seasonSaga"]


@pytest.mark.parametrize("selection,code", list(CODES.items()))
def test_each_champion_preview_uses_the_real_badge(app, client, selection, code):
    from app.badges import BADGES_BY_CODE

    with app.app_context():
        pid = player("SingleChampionStaff", "admin")
        login(client, pid)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 30)):
            data = state(client.get(BASE + "&champion=" + selection))
        story = data["rewind"]["seasonSaga"]
        assert story["demo"] is True
        assert story["count"] == 2
        assert [b["kind"] for b in story["beats"]] == ["winner", "winner_badge"]
        assert story["beats"][0]["visual"]["badgeCode"] == code
        badge = story["beats"][1]["visual"]["badge"]
        assert badge["code"] == code
        assert badge["name"] == BADGES_BY_CODE[code].name
        assert badge["rarity"] == BADGES_BY_CODE[code].rarity


@pytest.mark.parametrize("url", [
    "/rewind?champion=all",
    "/rewind?preview=1&champion=all",
    "/rewind?prototype=1&story=5&champion=all",
    "/rewind?preview=1&prototype=1&champion=all",
    "/rewind?preview=1&prototype=1&story=4&champion=all",
    BASE + "&champion=",
    BASE + "&champion=unknown",
    BASE + "&champion=season_champion",
    BASE + "&champion=all&champion=season",
])
def test_demo_rejects_missing_staff_preview_context_or_invalid_choice(app, client, url):
    with app.app_context():
        pid = player("InvalidChampionStaff", "admin")
        login(client, pid)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 30)):
            assert client.get(url).status_code == 404


def test_players_cannot_request_demos_even_after_finalization(app, client):
    with app.app_context():
        pid = player("ActualChampion")
        staff = player("FinalizedChampionStaff", "admin")
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-10-20", 95, True)
        season = get_season_for_date(date(2026, 10, 26))
        finalize_season_championships(season["id"], today=date(2026, 11, 2))

        with patch("app.main.routes.crew_today", return_value=date(2026, 11, 2)):
            login(client, pid)
            original = state(client.get("/rewind"))
            assert original["rewind"]["champion"] is True
            before = competition_state()
            for url in ("/rewind?champion=all", BASE + "&champion=all",
                        BASE + "&champion=season"):
                assert client.get(url).status_code == 404
            assert state(client.get("/rewind"))["rewind"] == original["rewind"]
            assert competition_state() == before

            login(client, staff)
            official = state(client.get(BASE))
            demo = state(client.get(BASE + "&champion=season"))
            assert demo["rewind"]["finalized"] is True
            assert demo["rewind"]["champion"] is False
            assert demo["rewind"]["badges"] == official["rewind"]["badges"]
            assert demo["rewind"]["seasonSaga"]["demo"] is True
            assert competition_state() == before

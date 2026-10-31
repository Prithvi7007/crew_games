"""Combined staff previews join championship openings to each player's real story."""
from datetime import date
from unittest.mock import patch

import pytest

from app.championships import finalize_season_championships
from app.db import finalize_game_stats, get_db, get_season_for_date, profile_user_key
from tests.test_rewind_champion_preview import (
    BASE, competition_state, login, player, state,
)

COMBINED = BASE + "&combined=1"


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_combined_preview_lists_every_player_and_joins_current_titles(app, client, role):
    with app.app_context():
        staff = player("CombinedStaff", role)
        leader = player("CombinedLeader")
        player("ZeroGames")
        finalize_game_stats(profile_user_key(leader), "trivia", "2026-10-20", 90, True)
        login(client, staff)
        before = competition_state()
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 30)):
            actual = state(client.get(BASE + "&player=CombinedLeader"))["rewind"]
            response = client.get(COMBINED + "&player=CombinedLeader")
            data = state(response)
            assert response.headers["Cache-Control"] == "private, no-store"
            assert set(data["rewindPreviewPlayers"]) == {"CombinedStaff", "CombinedLeader", "ZeroGames"}
            assert data["rewindCombinedPreview"]["selection"] == "results"
            assert data["rewindCombinedPreview"]["provisional"] is True
            beats = data["rewind"]["seasonSaga"]["beats"]
            assert [b["visual"]["badgeCode"] for b in beats if b["kind"] == "winner"] == [
                "season_champion", "season_trivia_master",
            ]
            assert all(b["visual"]["demo"] for b in beats[:4])
            assert all(b["visual"]["provisional"] for b in beats[:4])
            assert beats[4:] == actual["seasonSaga"]["beats"][1:]
            assert data["rewind"]["champion"] is False
            assert {k: v for k, v in data["rewind"].items() if k != "seasonSaga"} == {
                k: v for k, v in actual.items() if k != "seasonSaga"
            }
            zero = state(client.get(COMBINED + "&player=ZeroGames"))
            assert zero["rewind"]["seasonSaga"]["beats"][0]["kind"] == "welcome"
            assert not any(b["kind"] == "winner" for b in zero["rewind"]["seasonSaga"]["beats"])
            assert zero["rewind"]["points"] == 0
        assert competition_state() == before
        with client.session_transaction() as sess:
            assert sess["user"]["profile_id"] == staff


def test_combined_demo_keeps_full_story_and_never_duplicates_titles(app, client):
    with app.app_context():
        staff = player("CombinedDemoStaff", "admin")
        leader = player("CombinedDemoLeader")
        finalize_game_stats(profile_user_key(leader), "word", "2026-10-21", 80, True)
        season = get_season_for_date(date(2026, 10, 26))
        finalize_season_championships(season["id"], today=date(2026, 11, 2))
        login(client, staff)
        before = competition_state()
        with patch("app.main.routes.crew_today", return_value=date(2026, 11, 2)):
            actual = state(client.get(BASE + "&player=CombinedDemoLeader"))["rewind"]
            combined = state(client.get(COMBINED + "&player=CombinedDemoLeader"))
            assert combined["rewind"]["seasonSaga"] == actual["seasonSaga"]
            assert combined["rewindCombinedPreview"]["provisional"] is False
            demo = state(client.get(COMBINED + "&player=CombinedDemoLeader&champion=all"))
            beats = demo["rewind"]["seasonSaga"]["beats"]
            assert [b["kind"] for b in beats[:10]] == ["winner", "winner_badge"] * 5
            assert beats[10:] == [
                b for b in actual["seasonSaga"]["beats"]
                if b["kind"] not in ("winner", "winner_badge", "welcome")
            ]
            assert demo["rewind"]["seasonSaga"]["count"] == len(beats)
            assert demo["rewindCombinedPreview"]["selection"] == "all"
        assert competition_state() == before


def test_tied_current_leaders_get_shared_preview_without_awards(app, client):
    with app.app_context():
        staff = player("TiedPreviewStaff", "admin")
        for name in ("TiedOne", "TiedTwo"):
            pid = player(name)
            finalize_game_stats(profile_user_key(pid), "word", "2026-10-21", 70, True)
        login(client, staff)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 30)):
            for name in ("TiedOne", "TiedTwo"):
                data = state(client.get(COMBINED + "&player=" + name))
                winners = [b for b in data["rewind"]["seasonSaga"]["beats"] if b["kind"] == "winner"]
                assert len(winners) == 2
                assert all(b["visual"]["shared"] for b in winners)
        assert get_db().execute("SELECT COUNT(*) AS n FROM season_badge_finalizations").fetchone()["n"] == 0
        assert get_db().execute("SELECT COUNT(*) AS n FROM badge_awards").fetchone()["n"] == 0


@pytest.mark.parametrize("url", [
    "/rewind?combined=1", "/rewind?preview=1&combined=1",
    "/rewind?prototype=1&story=5&combined=1",
    "/rewind?preview=1&prototype=1&story=4&combined=1",
    BASE + "&combined=", BASE + "&combined=0",
    COMBINED + "&combined=1", COMBINED + "&player=CombinedAccess&player=Other",
])
def test_combined_preview_rejects_invalid_context_and_ambiguous_parameters(app, client, url):
    with app.app_context():
        staff = player("CombinedAccess", "admin")
        login(client, staff)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 30)):
            assert client.get(url).status_code == 404


def test_public_rewind_never_exposes_roster_or_combined_controls(app, client):
    with app.app_context():
        pid = player("CombinedPublic")
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-10-20", 80, True)
        season = get_season_for_date(date(2026, 10, 26))
        finalize_season_championships(season["id"], today=date(2026, 11, 2))
        login(client, pid)
        with patch("app.main.routes.crew_today", return_value=date(2026, 11, 2)):
            for url in (COMBINED, "/rewind?combined=1"):
                assert client.get(url).status_code == 404
            public = state(client.get("/rewind"))
            assert not public.get("rewindPreviewPlayers")
            assert not public.get("rewindCombinedPreview")

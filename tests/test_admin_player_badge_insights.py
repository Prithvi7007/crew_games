"""Admin badge insights use only verified awards and season-scoped completions."""

from datetime import date
from pathlib import Path

from app.badge_store import award_badges, get_badge_awards, set_showcase_slot
from app.db import (
    create_season, finalize_game_stats, get_db, get_season_for_date,
    profile_user_key,
)
from tests.test_v2_access import _profile, _sign_in


def _seed(app):
    player = _profile(app, "InsightChampion")
    teammate = _profile(app, "InsightTeammate")
    with app.app_context():
        first = get_season_for_date(date(2026, 10, 20))
        winter = create_season("Winter Crew", date(2027, 1, 4), date(2027, 1, 29))
        award_badges(player, first["id"], ("case_closed", "sharp_instincts"))
        award_badges(player, winter["id"], ("word_wizard",))
        equipped_id = next(
            int(row["id"]) for row in get_badge_awards(player, first["id"])
            if row["badge_code"] == "case_closed"
        )
        set_showcase_slot(player, 1, equipped_id)

        finalize_game_stats(profile_user_key(player), "mystery", "2026-10-19", 100, True, competitive=True)
        finalize_game_stats(profile_user_key(player), "trivia", "2026-10-20", 60, True, competitive=True)
        finalize_game_stats(profile_user_key(player), "word", "2026-10-21", 45, True, competitive=False)
        finalize_game_stats(profile_user_key(player), "word", "2027-01-06", 95, True, competitive=True)
        finalize_game_stats(profile_user_key(teammate), "mystery", "2026-10-19", 75, True, competitive=True)
        return player, teammate, first["id"], winter["id"]


def test_directory_shows_persisted_badges_and_equipped_season_without_preview(app):
    player, teammate, season_id, winter_id = _seed(app)
    admin_id = _profile(app, "InsightDirectoryAdmin", "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)
    with client.session_transaction() as session:
        session["trophy_preview_badge_code"] = "unicorn"

    html = client.get("/admin/players?q=Insight").get_data(as_text=True)
    assert "InsightChampion" in html and "InsightTeammate" in html
    assert "Equipped: Case Closed · S01" in html
    assert 'class="admin-directory-badges"' in html
    assert "None equipped" in html
    assert "v25-admin-badge-insights.css" in html
    assert "Unicorn" not in html

    from app.admin.player_insights import directory_badge_insights
    with app.app_context():
        results = directory_badge_insights([player, teammate])
    assert results[player]["badge_count"] == 3
    assert results[player]["equipped_badge"]["name"] == "Case Closed"
    assert results[teammate]["badge_count"] == 0
    assert results[teammate]["equipped_badge"] is None


def test_season_performance_separates_competitive_practice_and_other_seasons(app):
    player, _, first_id, winter_id = _seed(app)
    admin_id = _profile(app, "InsightSeasonAdmin", "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)

    first_html = client.get(f"/admin/players/{player}?season={first_id}").get_data(as_text=True)
    assert "Season performance &amp; badges" in first_html
    assert "160" in first_html
    assert "S01" in first_html
    assert "Case Closed" in first_html
    assert "Sharp Instincts" in first_html
    assert "Equipped" in first_html
    assert "Competitive" in first_html or "COMPETITIVE" in first_html

    winter_html = client.get(f"/admin/players/{player}?season={winter_id}").get_data(as_text=True)
    assert "Winter Crew" in winter_html
    assert "Word Wizard" in winter_html
    assert "Case Closed" in winter_html  # Profile's global equipped badge, not an S02 award.
    assert "No badges earned in this season yet." not in winter_html

    from app.admin.player_insights import player_season_insights
    with app.app_context():
        first = player_season_insights(player, first_id)
        winter = player_season_insights(player, winter_id)

    assert first["performance"]["points"] == 160
    assert first["performance"]["competitive_games"] == 2
    assert first["performance"]["practice_games"] == 1
    assert len(first["awards"]) == 2
    assert sum(award["equipped"] for award in first["awards"]) == 1

    assert winter["performance"]["points"] == 95
    assert winter["performance"]["competitive_games"] == 1
    assert winter["performance"]["practice_games"] == 0
    assert [award["code"] for award in winter["awards"]] == ["word_wizard"]
    assert not winter["awards"][0]["equipped"]
    assert winter["equipped_badge"]["season_number"] == 1


def test_invalid_season_selector_falls_back_without_exposing_other_players(app):
    player, teammate, first_id, _ = _seed(app)
    admin_id = _profile(app, "InsightInvalidSeasonAdmin", "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)
    for bad in ("not-a-season", "-50", "99999999"):
        response = client.get(f"/admin/players/{player}?season={bad}")
        assert response.status_code == 200
        assert "Season performance" in response.get_data(as_text=True)
    from app.admin.player_insights import player_season_insights
    with app.app_context():
        result = player_season_insights(player, "not-a-season")
        assert result["season"]["id"] == first_id
        assert len(result["awards"]) == 2


def test_player_cannot_reach_admin_badge_insights(app):
    player, _, _, _ = _seed(app)
    client = app.test_client()
    _sign_in(client, app, player)
    assert client.get("/admin/players").status_code == 302
    assert client.get(f"/admin/players/{player}").status_code == 302


def test_badge_views_do_not_modify_awards_or_player_showcase(app):
    player, _, first_id, _ = _seed(app)
    admin_id = _profile(app, "InsightReadonlyAdmin", "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)
    with app.app_context():
        before = [
            get_db().execute("SELECT COUNT(*) AS n FROM badge_awards").fetchone()["n"],
            get_db().execute("SELECT COUNT(*) AS n FROM badge_showcase").fetchone()["n"],
        ]
    client.get("/admin/players")
    client.get(f"/admin/players/{player}?season={first_id}")
    with app.app_context():
        after = [
            get_db().execute("SELECT COUNT(*) AS n FROM badge_awards").fetchone()["n"],
            get_db().execute("SELECT COUNT(*) AS n FROM badge_showcase").fetchone()["n"],
        ]
    assert before == after


def test_badge_insight_styles_and_schema_are_scoped_to_admin():
    root = Path(__file__).resolve().parents[1]
    css = (root / "app/static/css/v25-admin-badge-insights.css").read_text(encoding="utf-8")
    route = (root / "app/admin/routes.py").read_text(encoding="utf-8")
    module = (root / "app/admin/player_insights.py").read_text(encoding="utf-8")
    assert ".admin-player-badge-insights" in css
    assert "@media(max-width:760px)" in css
    assert 'badge_insights=player_season_insights(' in route
    assert "directory_badge_insights([row" in route
    assert "FROM badge_awards" in module
    assert "badge_showcase" in module
    assert "competitive = 1" in module
    assert "INSERT INTO" not in module and "UPDATE " not in module and "DELETE FROM" not in module

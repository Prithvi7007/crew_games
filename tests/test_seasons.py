from datetime import date
from pathlib import Path

from werkzeug.security import generate_password_hash

from app.db import (
    create_profile,
    finalize_game_stats,
    get_leaderboard,
    get_season_by_id,
    get_season_for_date,
    get_season_summary,
    list_seasons,
    profile_user_key,
    update_profile_role,
)
from app.migrations import HEAD_REVISION, current_revision


ROOT = Path(__file__).resolve().parents[1]


def _profile(app, username, role="player"):
    with app.app_context():
        profile = create_profile(
            username,
            generate_password_hash("correct horse battery staple"),
            "⭐",
            generate_password_hash("ORBIT-NOVA-COMET-RIVER-ABCD"),
        )
        profile_id = int(profile["id"])
        if role != "player":
            update_profile_role(profile_id, role)
        return profile_id


def _sign_in(client, app, profile_id):
    from app.db import get_profile_by_id

    with app.app_context():
        profile = get_profile_by_id(profile_id)
        user = {
            "profile_id": profile_id,
            "username": profile["username"],
            "avatar": profile["avatar"],
            "role": profile["role"],
            "user_key": profile_user_key(profile_id),
            "session_version": int(profile["session_version"]),
        }
    client.get("/login")
    with client.session_transaction() as session:
        session["user"] = user
        return session["csrf_token"]


def test_seasons_migration_is_active_and_launch_season_is_seeded(app):
    assert HEAD_REVISION == "v14_seasons"
    assert current_revision(app.config["DATABASE_URL"]) == "v14_seasons"

    with app.app_context():
        season = get_season_for_date(date(2026, 10, 7))

    assert season["number"] == 1
    assert season["name"] == "Launch Season"
    assert season["start_date"] == date(2026, 9, 21)
    assert season["end_date"] == date(2026, 10, 30)
    assert season["weeks_total"] == 6
    assert season["games_total"] == 24
    assert season["max_points"] == 2400


def test_launch_season_boundaries_and_week_numbers(app):
    with app.app_context():
        assert get_season_for_date(date(2026, 9, 20)) is None
        assert get_season_for_date(date(2026, 9, 21))["week_number"] == 1
        assert get_season_for_date(date(2026, 10, 5))["week_number"] == 3
        assert get_season_for_date(date(2026, 10, 26))["week_number"] == 6
        assert get_season_for_date(date(2026, 10, 30))["week_number"] == 6
        assert get_season_for_date(date(2026, 10, 31)) is None


def test_season_summary_uses_competitive_points_only(app):
    profile_id = _profile(app, "SeasonScorer")
    user_key = profile_user_key(profile_id)

    with app.app_context():
        finalize_game_stats(user_key, "word", "2026-09-23", 100, True, competitive=True)
        finalize_game_stats(user_key, "mystery", "2026-09-28", 75, True, competitive=False)
        summary = get_season_summary(user_key, date(2026, 10, 7))

    assert summary["points"] == 100
    assert summary["completed"] == 1
    assert summary["rank"] == 1


def test_rankings_support_season_and_ignore_archive_points(app):
    alpha = _profile(app, "SeasonAlpha")
    beta = _profile(app, "SeasonBeta")

    with app.app_context():
        finalize_game_stats(profile_user_key(alpha), "word", "2026-09-23", 100, True, competitive=True)
        finalize_game_stats(profile_user_key(beta), "word", "2026-09-23", 80, True, competitive=True)
        finalize_game_stats(profile_user_key(beta), "mystery", "2026-09-28", 100, True, competitive=False)
        board = get_leaderboard(
            "season",
            "all",
            reference_day=date(2026, 10, 7),
            current_profile_id=beta,
        )

    assert board["period_label"] == "Season 1 · Launch Season"
    assert [player["points"] for player in board["players"]] == [100, 80]
    assert board["me"]["rank"] == 2


def test_admin_settings_show_seeded_season(app):
    admin_id = _profile(app, "SeasonAdmin", "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)

    response = client.get("/admin/settings")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "SEASON MANAGEMENT" in html
    assert "Launch Season" in html
    assert "Sep 21" in html
    assert "Oct 30" in html


def test_admin_can_create_next_season(app):
    admin_id = _profile(app, "SeasonCreator", "admin")
    client = app.test_client()
    token = _sign_in(client, app, admin_id)

    response = client.post(
        "/admin/settings",
        data={
            "csrf_token": token,
            "action": "season_create",
            "season_name": "November Season",
            "season_start_date": "2026-11-02",
            "season_end_date": "2026-11-27",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        seasons = list_seasons(reference_day=date(2026, 10, 7))
    assert len(seasons) == 2
    created = next(item for item in seasons if item["number"] == 2)
    assert created["name"] == "November Season"
    assert created["start_date"] == date(2026, 11, 2)
    assert created["end_date"] == date(2026, 11, 27)


def test_admin_rejects_overlapping_or_bad_week_boundaries(app):
    admin_id = _profile(app, "SeasonValidator", "admin")
    client = app.test_client()
    token = _sign_in(client, app, admin_id)

    overlap = client.post(
        "/admin/settings",
        data={
            "csrf_token": token,
            "action": "season_create",
            "season_name": "Bad Overlap",
            "season_start_date": "2026-10-26",
            "season_end_date": "2026-11-20",
        },
        follow_redirects=True,
    )
    assert "overlap" in overlap.get_data(as_text=True).lower()

    bad_start = client.post(
        "/admin/settings",
        data={
            "csrf_token": token,
            "action": "season_create",
            "season_name": "Bad Start",
            "season_start_date": "2026-11-03",
            "season_end_date": "2026-11-27",
        },
        follow_redirects=True,
    )
    assert "monday" in bad_start.get_data(as_text=True).lower()

    with app.app_context():
        assert len(list_seasons()) == 1


def test_season_dates_lock_after_competitive_results_but_name_can_change(app):
    admin_id = _profile(app, "SeasonLocker", "admin")
    player_id = _profile(app, "SeasonPlayer")
    client = app.test_client()
    token = _sign_in(client, app, admin_id)

    with app.app_context():
        finalize_game_stats(
            profile_user_key(player_id),
            "word",
            "2026-09-23",
            100,
            True,
            competitive=True,
        )

    renamed = client.post(
        "/admin/settings",
        data={
            "csrf_token": token,
            "action": "season_update",
            "season_id": "1",
            "season_name": "Launch Championship",
            "season_start_date": "2026-09-21",
            "season_end_date": "2026-10-30",
        },
    )
    assert renamed.status_code == 302

    changed_dates = client.post(
        "/admin/settings",
        data={
            "csrf_token": token,
            "action": "season_update",
            "season_id": "1",
            "season_name": "Launch Championship",
            "season_start_date": "2026-09-21",
            "season_end_date": "2026-11-06",
        },
        follow_redirects=True,
    )
    assert "locked" in changed_dates.get_data(as_text=True).lower()

    with app.app_context():
        season = get_season_by_id(1)
    assert season["name"] == "Launch Championship"
    assert season["end_date"] == date(2026, 10, 30)


def test_player_templates_expose_season_context():
    today = (ROOT / "app" / "templates" / "_home_v17.html").read_text(encoding="utf-8")
    leaderboard = (ROOT / "app" / "templates" / "leaderboard.html").read_text(encoding="utf-8")
    profile = (ROOT / "app" / "templates" / "profile.html").read_text(encoding="utf-8")

    assert "SEASON {{ season.number }}" in today
    assert "SEASON PTS" in today
    assert "('season','Season')" in leaderboard
    assert "SEASON {{ season.number }} RANK" in profile
    assert "SEASON POINTS" in profile

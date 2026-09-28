from datetime import date

from werkzeug.security import generate_password_hash

from app.db import (
    create_profile,
    finalize_game_stats,
    get_competitive_rankings_between,
    profile_user_key,
)
from app.weekly_email import build_weekly_kickoff_context, render_weekly_kickoff


def _profile(app, username):
    with app.app_context():
        row = create_profile(
            username,
            generate_password_hash("correct horse battery staple"),
            "⭐",
            generate_password_hash("ORBIT-NOVA-COMET-RIVER-ABCD"),
        )
        return int(row["id"])


def test_competitive_rankings_exclude_archive_scores(app):
    alpha = _profile(app, "Alpha")
    beta = _profile(app, "Beta")

    with app.app_context():
        finalize_game_stats(profile_user_key(alpha), "mystery", "2026-09-21", 100, True, competitive=True)
        finalize_game_stats(profile_user_key(beta), "mystery", "2026-09-21", 90, True, competitive=False)

        rows = get_competitive_rankings_between(
            date(2026, 9, 21),
            date(2026, 9, 24),
            limit=10,
        )

    assert [row["username"] for row in rows] == ["Alpha"]
    assert rows[0]["points"] == 100
    assert rows[0]["rank"] == 1


def test_monday_context_freezes_rankings_at_previous_thursday(app):
    alpha = _profile(app, "Alpha")

    with app.app_context():
        finalize_game_stats(profile_user_key(alpha), "tick_tock", "2026-09-24", 80, True, competitive=True)
        finalize_game_stats(profile_user_key(alpha), "mystery", "2026-09-28", 100, True, competitive=True)

        context = build_weekly_kickoff_context(date(2026, 9, 28))

    assert context["previous_week_number"] == 1
    assert context["current_week_number"] == 2
    assert context["previous_leaders"][0]["points"] == 80
    assert context["season_leaders"][0]["points"] == 80


def test_weekly_email_renders_outlook_safe_html(app):
    alpha = _profile(app, "Alpha")

    with app.app_context():
        finalize_game_stats(profile_user_key(alpha), "word", "2026-09-23", 65, True, competitive=True)
        rendered = render_weekly_kickoff(date(2026, 9, 28))

    assert rendered["status"] == "ready"
    assert "CREW Week 01 Results" in rendered["subject"]
    assert "Week 02 Is Open" in rendered["subject"]
    assert "<table" in rendered["html"]
    assert "Alpha" in rendered["html"]
    assert "SEASON LEADERBOARD" in rendered["html"]
    assert "WEEK 02" in rendered["html"]

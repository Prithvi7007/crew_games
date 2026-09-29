from datetime import date

from werkzeug.security import generate_password_hash

from app.db import (
    create_profile,
    finalize_game_stats,
    get_competitive_rankings_between,
    profile_user_key,
    set_setting,
)
from app.weekly_email import (
    build_weekly_kickoff_context,
    render_weekly_kickoff,
    send_weekly_kickoff,
)


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
    assert context["reference_date_label"] == "September 28, 2026"
    assert context["games"][0]["date_label"] == "Sep 28"


def test_weekly_email_renders_outlook_safe_html(app):
    alpha = _profile(app, "Alpha")

    with app.app_context():
        finalize_game_stats(profile_user_key(alpha), "word", "2026-09-23", 65, True, competitive=True)
        rendered = render_weekly_kickoff(date(2026, 9, 28))

    assert rendered["status"] == "ready"
    assert rendered["subject"] == "CREW Games Weekly | Week 02 is Live"
    assert "<table" in rendered["html"]
    assert "Alpha" in rendered["html"]
    assert "Season Standings" in rendered["html"]
    assert "Week 02 is" in rendered["html"]
    assert ">Live</span>" in rendered["html"]
    assert "October Prize Update" in rendered["html"]
    assert "randomly selected participant" in rendered["html"]
    assert "Season Standings" in rendered["html"]
    assert "OPEN CREW GAMES" in rendered["html"]


def test_weekly_email_can_be_disabled_from_admin_setting(app):
    with app.app_context():
        set_setting("email.weekly_kickoff.enabled", "0")
        result = send_weekly_kickoff(
            reference_day=date(2026, 9, 28),
            force=True,
            dry_run=True,
        )

    assert result["status"] == "disabled"
    assert "disabled in Admin Studio" in result["reason"]


def test_weekly_email_uses_admin_recipient_override(app):
    with app.app_context():
        set_setting("email.weekly_kickoff.enabled", "1")
        set_setting("email.weekly_kickoff.to", "crew-list@example.com")
        result = send_weekly_kickoff(
            reference_day=date(2026, 9, 28),
            force=True,
            dry_run=True,
        )

    assert result["status"] == "dry_run"
    assert result["recipients"] == ["crew-list@example.com"]

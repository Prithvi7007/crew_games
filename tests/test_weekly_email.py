from datetime import date
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app.db import (
    create_profile,
    finalize_game_stats,
    get_competitive_rankings_between,
    get_rankings_between,
    get_leaderboard,
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


def _record_at(utc_timestamp, user_key, game_key, game_date, score, competitive):
    with patch("app.db._db_timestamp", return_value=utc_timestamp):
        finalize_game_stats(user_key, game_key, game_date, score, True, competitive=competitive)


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


def test_weekly_email_matches_public_rankings_including_catchup(app):
    alpha = _profile(app, "Alpha")
    beta = _profile(app, "Beta")
    with app.app_context():
        _record_at("2026-10-04T12:00:00", profile_user_key(alpha), "mystery", "2026-09-28", 70, True)
        _record_at("2026-10-04T12:00:00", profile_user_key(beta), "mystery", "2026-09-28", 90, False)
        _record_at("2026-10-04T12:00:00", profile_user_key(alpha), "tick_tock", "2026-10-01", 40, False)
        expected = get_rankings_between(date(2026, 9, 28), date(2026, 10, 1))
        context = build_weekly_kickoff_context(date(2026, 10, 5))
        public = get_leaderboard(period="last_week", reference_day=date(2026, 10, 5))

    assert [(x["username"], x["points"]) for x in context["previous_leaders"]] == [
        (x["username"], x["points"]) for x in public["players"]
    ]
    assert [(x["username"], x["points"]) for x in expected] == [
        ("Alpha", 110), ("Beta", 90)
    ]
    assert [(x["username"], x["points"]) for x in context["previous_leaders"]] == [
        ("Alpha", 110), ("Beta", 90)
    ]
    assert [(x["username"], x["points"]) for x in context["season_leaders"]] == [
        ("Alpha", 110), ("Beta", 90)
    ]


def test_monday_context_freezes_rankings_at_previous_sunday(app):
    alpha = _profile(app, "Alpha")

    with app.app_context():
        _record_at("2026-09-27T12:00:00", profile_user_key(alpha), "tick_tock", "2026-09-24", 80, True)
        _record_at("2026-09-28T12:00:00", profile_user_key(alpha), "mystery", "2026-09-28", 100, True)

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
        _record_at("2026-09-27T12:00:00", profile_user_key(alpha), "word", "2026-09-23", 65, True)
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

def test_force_resend_keeps_standard_newsletter_without_correction_notice(app):
    alpha = _profile(app, "Alpha")
    with app.app_context():
        _record_at("2026-09-27T12:00:00", profile_user_key(alpha),
                   "mystery", "2026-09-21", 80, False)
        set_setting("email.weekly_kickoff.to", "crew-list@example.com")
        set_setting("email.weekly_kickoff.2026-09-28", '{"resend_id":"already-sent"}')
        already_sent = send_weekly_kickoff(
            reference_day=date(2026, 9, 28), dry_run=True
        )
        result = send_weekly_kickoff(
            reference_day=date(2026, 9, 28), force=True, dry_run=True
        )

    assert already_sent["status"] == "already_sent"
    assert result["status"] == "dry_run"
    assert result["recipients"] == ["crew-list@example.com"]
    assert result["subject"] == "CREW Games Weekly | Week 02 is Live"
    assert "CORRECTION" not in result["html"]
    assert "CORRECTION" not in result["text"]
    assert "correction_notice" not in result["html"]
    assert "force-" in result["send_key"]
    assert result["context"]["previous_leaders"][0]["points"] == 80


def test_sunday_1159_eastern_included_monday_midnight_excluded(app):
    early = _profile(app, "SundayFinisher")
    late = _profile(app, "MondayFinisher")
    with app.app_context():
        # Oct 11, 2026 23:59:59 EDT = Oct 12 03:59:59 UTC.
        _record_at("2026-10-12T03:59:59", profile_user_key(early),
                   "tick_tock", "2026-10-08", 90, False)
        # Oct 12, 2026 00:00:00 EDT = Oct 12 04:00:00 UTC.
        _record_at("2026-10-12T04:00:00", profile_user_key(late),
                   "tick_tock", "2026-10-08", 100, False)
        context = build_weekly_kickoff_context(date(2026, 10, 12))

    assert context["previous_week_start"] == date(2026, 10, 5)
    assert context["previous_week_end"] == date(2026, 10, 11)
    assert context["previous_week_range"] == "Oct 5–11, 2026"
    assert [(row["username"], row["points"]) for row in context["previous_leaders"]] == [
        ("SundayFinisher", 90)
    ]
    assert [(row["username"], row["points"]) for row in context["season_leaders"]] == [
        ("SundayFinisher", 90)
    ]


from datetime import date
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app.db import (
    create_profile,
    create_season,
    finalize_game_stats,
    get_competitive_rankings_between,
    get_rankings_between,
    get_leaderboard,
    profile_user_key,
    set_setting,
)
from app.badge_store import award_badges, get_badge_awards, set_showcase_slot
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


def test_monday_context_uses_previous_week_game_dates(app):
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
    assert rendered["subject"] == "CREW Games Weekly | Season 1 — Week 02 is Live"
    assert "<table" in rendered["html"]
    assert "Alpha" in rendered["html"]
    assert "Season 1 Standings" in rendered["html"]
    assert "Week 02 is" in rendered["html"]
    assert ">Live</span>" in rendered["html"]
    assert "October Prize Update" in rendered["html"]
    assert "randomly selected participant" in rendered["html"]
    assert "Season 1 Standings" in rendered["html"]
    assert "PLAY THIS WEEK'S GAMES" in rendered["html"]
    assert "border:1px solid #4cc4ff" not in rendered["html"]
    assert "border:1px solid #2aa8ff" not in rendered["html"]
    assert rendered["html"].count("outline:0;box-shadow:none") == 2


def test_premium_weekly_email_keeps_dynamic_links_and_outlook_fallbacks(app):
    with app.app_context():
        rendered = render_weekly_kickoff(date(2026, 9, 28))

    html = rendered["html"]
    assert "THE WEEKLY PODIUM" in html
    assert "THE RACE FOR THE SEASON" in html
    assert "YOUR NEXT FOUR CHALLENGES" in html
    assert html.count("EXPLORE GAME") == 4
    assert "PLAY THIS WEEK'S GAMES" in html
    assert "VIEW FULL LEADERBOARD" in html
    assert "<!--[if mso]>" in html
    assert "background:#0b1e38" in html
    assert "backdrop-filter" not in html
    assert "<script" not in html


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
    assert result["subject"] == "CREW Games Weekly | Season 1 — Week 02 is Live"
    assert "CORRECTION" not in result["html"]
    assert "CORRECTION" not in result["text"]
    assert "correction_notice" not in result["html"]
    assert "force-" in result["send_key"]
    assert result["context"]["previous_leaders"][0]["points"] == 80


def test_email_includes_late_previous_week_catchup_at_generation(app):
    sunday = _profile(app, "SundayFinisher")
    monday_catchup = _profile(app, "MondayCatchup")
    new_week = _profile(app, "NewWeekPlayer")
    with app.app_context():
        # These completions are for Week 03 game dates, though one was
        # recorded Monday after the former Sunday-night cutoff.
        _record_at("2026-10-12T03:59:59", profile_user_key(sunday),
                   "tick_tock", "2026-10-08", 90, False)
        _record_at("2026-10-12T15:30:00", profile_user_key(monday_catchup),
                   "trivia", "2026-10-06", 100, False)
        # A Monday Week 04 game never counts toward the previous-week recap.
        _record_at("2026-10-12T15:30:00", profile_user_key(new_week),
                   "mystery", "2026-10-12", 100, True)
        context = build_weekly_kickoff_context(date(2026, 10, 12))
        rendered = render_weekly_kickoff(date(2026, 10, 12))

    assert context["previous_week_start"] == date(2026, 10, 5)
    assert context["previous_week_end"] == date(2026, 10, 11)
    assert context["previous_week_range"] == "Oct 5–11, 2026"
    expected = [("MondayCatchup", 100), ("SundayFinisher", 90)]
    assert [(row["username"], row["points"]) for row in context["previous_leaders"]] == expected
    assert [(row["username"], row["points"]) for row in context["season_leaders"]] == expected
    assert "Scores as of this email" in rendered["html"]
    assert "Sunday 11:59" not in rendered["html"]
    assert "CORRECTION" not in rendered["html"]



def test_season_one_finale_week_announces_both_gift_cards(app):
    with app.app_context():
        rendered = render_weekly_kickoff(date(2026, 10, 26))

    context = rendered["context"]
    assert context["current_week_number"] == 6
    assert context["is_season_one_final_week"] is True
    assert context["previous_week_range"] == "Oct 19–25, 2026"
    assert rendered["subject"] == "CREW Games Weekly | Season One Finale — Week 06"
    assert "Season One" in rendered["html"]
    assert "Finale</span>" in rendered["html"]
    assert "Season One: Final Week" in rendered["html"]
    assert "Friday, Oct 30" in rendered["html"]
    assert "Four games left, two gift cards up for grabs!" in rendered["html"]
    assert "One for the top cumulative scorer, one by random draw." in rendered["html"]
    assert "Winners confirmed next week." in rendered["html"]
    assert "Winners confirmed next week." in rendered["text"]
    assert "Week 05 Final Standings" in rendered["html"]
    assert "Season 1 Standings" in rendered["html"]
    assert "the final four games" in rendered["text"].lower()
    assert "OCTOBER PRIZE UPDATE" not in rendered["text"]
    assert "one by random draw" in rendered["text"]


def test_finale_announcement_does_not_repeat_after_season(app):
    with app.app_context():
        before = render_weekly_kickoff(date(2026, 10, 19))
        create_season("November Season", "2026-11-02", "2026-11-27")
        after = render_weekly_kickoff(date(2026, 11, 2))

    assert before["context"]["prize_heading"] == "October Prize Update"
    assert "October Prize Update" in before["html"]
    assert after["context"]["is_season_one_final_week"] is False
    assert after["context"]["prize_heading"] is None
    assert "Season One: Final Week" not in after["html"]
    assert "October Prize Update" not in after["html"]
    assert "randomly selected participant" not in after["text"]

def test_weekly_email_avatar_and_equipped_badge_in_podium_and_season_rows(app):
    alpha = _profile(app, "AwardedAlpha")
    beta = _profile(app, "PlainBeta")
    with app.app_context():
        from app.db import get_season_for_date, update_profile_avatar
        season = get_season_for_date(date(2026, 10, 19))
        update_profile_avatar(alpha, "🚀")
        update_profile_avatar(beta, "🐻")
        award_badges(alpha, season["id"], ["word_wizard"])
        award_id = next(int(a["id"]) for a in get_badge_awards(alpha, season["id"])
                        if a["badge_code"] == "word_wizard")
        set_showcase_slot(alpha, 1, award_id)
        finalize_game_stats(profile_user_key(alpha), "word", "2026-10-21", 100, True)
        finalize_game_stats(profile_user_key(beta), "word", "2026-10-21", 80, True)
        rendered = render_weekly_kickoff(date(2026, 10, 26))

    previous = rendered["context"]["previous_leaders"]
    assert previous[0]["avatar"] == "🚀"
    assert previous[0]["equippedBadge"]["code"] == "word_wizard"
    assert previous[1]["equippedBadge"] is None
    assert rendered["context"]["season_leaders"][0]["equippedBadge"]["seasonNumber"] == 1
    assert rendered["html"].count("Word Wizard") >= 2
    assert rendered["html"].count("S01") >= 2
    assert "#9dafbe" in rendered["html"]
    assert "🚀" in rendered["html"] and "🐻" in rendered["html"]
    assert "Word Wizard" not in rendered["text"]
    assert '>✦</td>' not in rendered["html"]
    assert 'title="Word Wizard"' not in rendered["html"]


def test_weekly_email_never_shows_unpublished_or_unequipped_badges(app):
    alpha = _profile(app, "QuietAward")
    with app.app_context():
        from app.db import get_season_for_date
        season = get_season_for_date(date(2026, 10, 12))
        award_badges(alpha, season["id"], ["case_closed"])
        finalize_game_stats(profile_user_key(alpha), "mystery", "2026-10-08", 75, True)
        before = render_weekly_kickoff(date(2026, 10, 12))
        after = render_weekly_kickoff(date(2026, 10, 19))

    assert before["context"]["previous_leaders"][0]["equippedBadge"] is None
    assert after["context"]["season_leaders"][0]["equippedBadge"] is None
    assert "Case Closed" not in before["html"]
    assert "Case Closed" not in after["html"]


def test_email_uses_real_badge_label_not_detached_icon_or_duplicate_rank(app):
    alpha = _profile(app, "CompactWinner")
    with app.app_context():
        from app.db import get_season_for_date
        season = get_season_for_date(date(2026, 10, 19))
        award_badges(alpha, season["id"], ["word_wizard"])
        award_id = next(int(a["id"]) for a in get_badge_awards(alpha, season["id"])
                        if a["badge_code"] == "word_wizard")
        set_showcase_slot(alpha, 1, award_id)
        finalize_game_stats(profile_user_key(alpha), "word", "2026-10-21", 100, True)
        rendered = render_weekly_kickoff(date(2026, 10, 26))

    html = rendered["html"]
    assert "🥇" in html
    assert "CompactWinner" in html
    assert "Word Wizard" in html
    assert "S01" in html
    assert ">✦</td>" not in html
    assert "#{{ player.podium_rank }}" not in html
    assert "email_avatar" not in html


def test_weekly_email_skips_when_there_is_no_active_season(app):
    with app.app_context():
        rendered = render_weekly_kickoff(date(2026, 11, 2))

    assert rendered["status"] == "skipped"
    assert "no active CREW season" in rendered["reason"]
    assert rendered["context"]["active_season"] is None


def test_season_two_week_one_resets_newsletter_and_skips_last_season_recap(app):
    season_one_player = _profile(app, "OldChampion")
    with app.app_context():
        finalize_game_stats(
            profile_user_key(season_one_player), "mystery", "2026-10-26", 100, True
        )
        create_season("November Season", "2026-11-02", "2026-11-27")
        rendered = render_weekly_kickoff(date(2026, 11, 2))

    context = rendered["context"]
    assert rendered["status"] == "ready"
    assert rendered["subject"] == "CREW Games Weekly | Season 2 — Week 01 is Live"
    assert context["season_number"] == 2
    assert context["current_week_number"] == 1
    assert context["previous_week_number"] == 0
    assert context["previous_leaders"] == []
    assert context["season_leaders"] == []
    assert "Season 2" in rendered["html"]
    assert "Week 00" not in rendered["html"]
    assert "Final Standings" not in rendered["html"]
    assert "OldChampion" not in rendered["html"]
    assert "Week 00" not in rendered["text"]
    assert "SEASON 2 STANDINGS" in rendered["text"]


def test_season_two_week_two_recap_uses_only_season_two_scores(app):
    old_player = _profile(app, "SeasonOneOnly")
    new_player = _profile(app, "SeasonTwoLeader")
    with app.app_context():
        create_season("November Season", "2026-11-02", "2026-11-27")
        finalize_game_stats(
            profile_user_key(old_player), "mystery", "2026-10-26", 100, True
        )
        finalize_game_stats(
            profile_user_key(new_player), "mystery", "2026-11-02", 85, True
        )
        rendered = render_weekly_kickoff(date(2026, 11, 9))

    context = rendered["context"]
    assert rendered["status"] == "ready"
    assert rendered["subject"] == "CREW Games Weekly | Season 2 — Week 02 is Live"
    assert context["current_week_number"] == 2
    assert context["previous_week_number"] == 1
    assert [(row["username"], row["points"]) for row in context["previous_leaders"]] == [
        ("SeasonTwoLeader", 85)
    ]
    assert [(row["username"], row["points"]) for row in context["season_leaders"]] == [
        ("SeasonTwoLeader", 85)
    ]
    assert "Season 2 · Week 01 Final Standings" in rendered["html"]
    assert "Season 2 Standings" in rendered["html"]
    assert "SeasonOneOnly" not in rendered["html"]
    assert "Week 08" not in rendered["html"]


def test_editorial_week_two_highlights_real_winner_and_skips_duplicate_standings(app):
    winner = _profile(app, "WinnerA")
    runner = _profile(app, "RunnerB")
    third = _profile(app, "ThirdC")
    fourth = _profile(app, "FourthD")
    with app.app_context():
        create_season("November Season", "2026-11-02", "2026-11-27")
        for profile_id, score in [(winner, 90), (runner, 70), (third, 60), (fourth, 40)]:
            finalize_game_stats(
                profile_user_key(profile_id), "mystery", "2026-11-02", score, True
            )
        rendered = render_weekly_kickoff(date(2026, 11, 9))

    context, html = rendered["context"], rendered["html"]
    assert context["week_champion"]["username"] == "WinnerA"
    assert [p["username"] for p in context["week_chasers"]] == ["RunnerB", "ThirdC"]
    assert context["lead_gap"] == 20
    assert context["season_is_opening_round"] is True
    assert context["points_available"] == 400
    assert "WinnerA finished Week 01 with 90 points." in html
    assert "RunnerB is just 20 points back." in html
    assert "JUST 20 PTS BETWEEN #1 AND #2" in html
    assert "NEXT IN LINE" in html
    assert "FourthD" in html
    assert "Season 2 Standings" in html
    assert "SEASON PTS" not in html  # No duplicate leaderboard table in first recap.
    assert "The opening week sets the first season order." in html
    assert html.count("EXPLORE GAME") == 4
    for target in ("/mystery", "/trivia", "/word", "/tick-tock"):
        assert target in html


def test_editorial_weekly_podium_handles_ties_without_false_lead_claim(app):
    first = _profile(app, "TiedA")
    second = _profile(app, "TiedB")
    with app.app_context():
        create_season("November Season", "2026-11-02", "2026-11-27")
        finalize_game_stats(profile_user_key(first), "mystery", "2026-11-02", 75, True)
        finalize_game_stats(profile_user_key(second), "mystery", "2026-11-02", 75, True)
        rendered = render_weekly_kickoff(date(2026, 11, 9))

    assert rendered["context"]["lead_gap"] == 0
    assert "JOINT WEEKLY LEAD" in rendered["html"]
    assert "TIED AT THE TOP" in rendered["html"]
    assert "just 0 points back" not in rendered["html"]


def test_editorial_later_weeks_show_compact_season_rankings(app):
    alpha = _profile(app, "SeasonAlpha")
    beta = _profile(app, "SeasonBeta")
    with app.app_context():
        create_season("November Season", "2026-11-02", "2026-11-27")
        finalize_game_stats(profile_user_key(alpha), "mystery", "2026-11-02", 90, True)
        finalize_game_stats(profile_user_key(beta), "mystery", "2026-11-02", 70, True)
        finalize_game_stats(profile_user_key(beta), "mystery", "2026-11-09", 100, True)
        rendered = render_weekly_kickoff(date(2026, 11, 16))

    context, html = rendered["context"], rendered["html"]
    assert context["previous_week_number"] == 2
    assert context["season_is_opening_round"] is False
    assert context["week_champion"]["username"] == "SeasonBeta"
    assert context["season_top_five"][0]["username"] == "SeasonBeta"
    assert context["season_top_five"][0]["points"] == 170
    assert "SEASON PTS" in html
    assert "Season 2 Standings" in html


def test_editorial_new_season_starts_without_podium_or_invented_results(app):
    with app.app_context():
        create_season("November Season", "2026-11-02", "2026-11-27")
        rendered = render_weekly_kickoff(date(2026, 11, 2))

    assert rendered["status"] == "ready"
    assert rendered["context"]["week_champion"] is None
    assert rendered["context"]["lead_gap"] is None
    assert "THE WEEKLY PODIUM" not in rendered["html"]
    assert "Everyone begins at zero." in rendered["html"]
    assert rendered["html"].count("EXPLORE GAME") == 4

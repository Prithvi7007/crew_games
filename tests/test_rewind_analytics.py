"""Evidence-first Rewind stories: defensible samples, real comparisons and privacy."""
from datetime import date

from app.rewind_analytics import build_rewind_analytics


START = date(2026, 9, 21)
NAMES = {1: "SamIam", 2: "Pat", 3: "Rey", 4: "Lee"}


def row(pid, game, day, score):
    return {"profile_id": pid, "game_key": game,
            "game_date": day, "score": score}


def findings(rows, *, name_id=1, weeks_total=6, rank=1):
    mine = [item for item in rows if item["profile_id"] == name_id]
    return build_rewind_analytics(
        mine, rows, profile_id=name_id, season_start=START,
        weeks_total=weeks_total, profile_names=NAMES, rank=rank,
    )


def test_samiam_style_story_reveals_same_puzzle_strength_week_and_rival():
    # Three peers play the *same* puzzle as the player. The other player
    # remains a peer even when they complete multiple weeks.
    rows = [
        row(1, "trivia", "2026-09-22", 100),
        row(1, "word", "2026-09-23", 100),
        row(1, "trivia", "2026-09-29", 70),
        row(2, "trivia", "2026-09-22", 90),
        row(2, "word", "2026-09-23", 90),
        row(2, "trivia", "2026-09-29", 80),
        row(3, "trivia", "2026-09-22", 75),
        row(3, "word", "2026-09-23", 75),
        row(3, "trivia", "2026-09-29", 100),
        row(4, "trivia", "2026-09-22", 55),
        row(4, "word", "2026-09-23", 55),
        row(4, "trivia", "2026-09-29", 70),
    ]
    report = findings(rows)
    cards = {card["key"]: card for card in report["cards"]}
    assert report["sample"] == {
        "completedGames": 3, "weeksActive": 2, "otherActivePlayers": 3,
    }
    assert cards["same_puzzle"]["metric"] == "3 / 3"
    assert "that exact puzzle" in cards["same_puzzle"]["story"]
    assert cards["relative_strength"]["metric"] == "+7 pts"
    assert "2 of your games and 3 other" in cards["relative_strength"]["evidence"]
    assert cards["pivotal_week"]["metric"] == "+3 places"
    assert "instead of #1" in cards["pivotal_week"]["story"]
    assert cards["closest_rival"]["metric"] == "10 pts apart"
    assert "Pat" in cards["closest_rival"]["story"]
    assert "Hypothetical" in cards["pivotal_week"]["method"]


def test_small_samples_do_not_create_false_peer_insights():
    rows = [row(1, "word", "2026-09-23", 100)]
    report = findings(rows)
    assert report["sample"]["otherActivePlayers"] == 0
    assert report["cards"] == []


def test_ties_not_described_as_outscoring_and_comparable_game_types_only():
    # Identical scores are ties, not wins; no one should be "outscored".
    peers = [row(pid, "trivia", "2026-09-22", 80) for pid in (2, 3, 4)]
    report = findings([row(1, "trivia", "2026-09-22", 80)] + peers)
    assert not any(c["key"] == "same_puzzle" for c in report["cards"])
    assert not any(c["key"] == "relative_strength" for c in report["cards"])

    # A high-scoring Wordle second half must not be compared to first-half
    # Trivia and interpreted as personal improvement.
    mixed = [
        row(1, "trivia", "2026-09-22", 30),
        row(1, "trivia", "2026-09-29", 40),
        row(1, "word", "2026-10-14", 100),
        row(1, "word", "2026-10-21", 95),
    ]
    assert not any(c["key"] == "matched_momentum"
                   for c in findings(mixed)["cards"])


def test_momentum_must_repeatedly_compare_the_same_game():
    rows = [
        row(1, "word", "2026-09-23", 50),
        row(1, "word", "2026-09-30", 60),
        row(1, "word", "2026-10-14", 90),
        row(1, "word", "2026-10-21", 100),
    ]
    card = next(c for c in findings(rows)["cards"]
                if c["key"] == "matched_momentum")
    assert card["metric"] == "+40 pts/game"
    assert "2 earlier and 2 later" in card["evidence"]
    assert "same game types: Wordle" in card["story"]


def test_analyst_notebook_is_staff_only_readonly_and_does_not_expand_player_preview(
        app, client):
    # Existing test helpers are local to this module; reuse the exact route
    # contract without requiring an authenticated production connection.
    from unittest.mock import patch
    from werkzeug.security import generate_password_hash
    from app.db import (create_profile, finalize_game_stats,
                        get_profile_by_id, profile_user_key, update_profile_role)
    from app.schedule import crew_today

    def profile(username, staff=False):
        p = create_profile(username, generate_password_hash("test-pass-123"),
                           "⭐", generate_password_hash("test-key-123"))
        pid = int(p["id"])
        if staff:
            update_profile_role(pid, "admin")
        return pid

    def login(pid):
        user = get_profile_by_id(pid)
        client.get("/login")
        with client.session_transaction() as session:
            session["user"] = {
                "profile_id": pid, "username": user["username"],
                "role": user["role"], "avatar": user["avatar"],
                "user_key": profile_user_key(pid),
                "session_version": int(user["session_version"]),
            }

    with app.app_context():
        sid = profile("SamIam")
        aid = profile("AnalystAdmin", staff=True)
        finalize_game_stats(profile_user_key(sid), "trivia", "2026-09-22",
                            85, True)
        login(aid)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 26)):
            allowed = client.get(
                "/rewind?preview=1&prototype=1&analysis=1&player=SamIam")
            assert allowed.status_code == 200
            assert b'"rewindAnalyticsPreview": true' in allowed.data
            assert b'"analyticsStory":' in allowed.data
            assert allowed.headers["Cache-Control"] == "private, no-store"
            assert client.get(
                "/rewind?preview=1&analysis=1&player=SamIam").status_code == 404
            assert client.get("/rewind?analysis=1").status_code == 404
            assert client.get(
                "/rewind?prototype=1&analysis=1&player=SamIam").status_code == 404
        login(sid)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 26)):
            assert client.get(
                "/rewind?preview=1&prototype=1&analysis=1&player=SamIam").status_code == 404


def test_rival_claim_needs_a_meaningful_peer_field():
    rows = [row(1, "trivia", "2026-09-22", 100),
            row(2, "trivia", "2026-09-22", 95)]
    report = findings(rows)
    assert not any(c["key"] == "closest_rival" for c in report["cards"])


def test_analytics_preview_copies_inspectable_evidence_without_export_endpoint():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    notebook = (root / "frontend/src/player/RewindAnalysisNotebook.jsx").read_text()
    app_entry = (root / "frontend/src/player/main.jsx").read_text()
    assert "onClick={copyFindings}" in notebook
    assert "navigator.clipboard?.writeText" in notebook
    assert "Method: '+card.method" in notebook
    assert "data.rewindAnalyticsPreview === true" in app_entry
    assert "RewindAnalysisNotebook" in app_entry
    assert "rewindAnalysisPreview" not in notebook  # server must enforce permission

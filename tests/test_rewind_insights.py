"""Rewind play-style insights use real scored rows and avoid small-sample claims."""
from datetime import date

from app.rewind_insights import build_rewind_insights


START = date(2026, 9, 21)


def row(pid, key, day, points):
    return {
        "profile_id": pid, "game_key": key,
        "game_date": day, "score": points,
    }


def insights(rows, *, user=1, signature=None, participants=4, rank=1):
    mine = [r for r in rows if r["profile_id"] == user]
    return build_rewind_insights(
        mine, rows, profile_id=user, season_start=START, weeks_total=6,
        signature=signature, rank=rank, participants=participants,
        points=sum(r["score"] for r in mine),
    )


def test_personalized_analytics_use_scores_per_game_not_total_weekly_points():
    mine = [
        row(1, "trivia", "2026-09-22", 40),
        row(1, "trivia", "2026-09-29", 60),
        row(1, "word", "2026-10-06", 80),
        row(1, "word", "2026-10-14", 100),
        row(1, "mystery", "2026-10-19", 90),
        row(1, "tick_tock", "2026-10-29", 90),
    ]
    data = insights(mine)
    assert data["averageScore"] == 77
    assert data["gamesTried"] == 4
    assert data["longestWeeklyStreak"] == 6
    assert data["momentum"] == {
        "firstAverage": 60, "secondAverage": 93,
        "change": 33, "direction": "up",
    }
    assert data["highestGame"] == {
        "score": 100, "game": "Wordle Wednesday", "week": 4,
    }
    assert data["playStyle"]["title"] == "THE ALL-ROUNDER"
    assert "four CREW game types" in data["playStyle"]["evidence"]


def test_peer_benchmark_requires_three_distinct_other_players_and_two_personal_attempts():
    mine = [
        row(1, "trivia", "2026-09-22", 90),
        row(1, "trivia", "2026-09-29", 100),
    ]
    signature = {"key": "trivia", "name": "Trivia Tuesday", "average": 95, "played": 2}
    peers = [
        row(2, "trivia", "2026-09-22", 40),
        row(2, "trivia", "2026-09-29", 60),
        row(3, "trivia", "2026-09-22", 70),
        row(4, "trivia", "2026-09-22", 75),
    ]
    assert insights(mine + peers[:3], signature=signature)["peerComparison"] is None
    benchmark = insights(mine + peers, signature=signature)["peerComparison"]
    assert benchmark == {
        "game": "Trivia Tuesday", "yourAverage": 95,
        "crewAverage": 65, "difference": 30, "playersCompared": 3,
    }
    assert insights(mine[:1] + peers, signature=signature)["peerComparison"] is None


def test_momentum_requires_two_games_in_each_half_and_strict_outpaced_not_ties():
    mine = [row(1, "word", "2026-09-23", 100)]
    peers = [
        row(2, "word", "2026-09-23", 100),
        row(3, "word", "2026-09-23", 70),
        row(4, "word", "2026-09-23", 30),
    ]
    data = insights(mine + peers)
    assert data["momentum"] is None
    assert data["outpacedPercent"] == 67
    assert data["playStyle"]["title"] == "THE CHALLENGER"


def test_no_games_is_kind_and_never_invents_a_play_style_benchmark():
    data = insights([])
    assert data["averageScore"] is None
    assert data["longestWeeklyStreak"] == 0
    assert data["highestGame"] is None
    assert data["momentum"] is None
    assert data["peerComparison"] is None
    assert data["outpacedPercent"] is None
    assert data["playStyle"]["title"] == "THE NEXT CHAPTER"

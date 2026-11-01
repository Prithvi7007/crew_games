"""Season and weekly podiums describe every eligible viewer's actual results."""
from datetime import date, timedelta

import pytest

from app.rewind_saga import build_season_saga


def story(pid, rows, *, winners=None, awarded=(), names=None):
    names = names or {1: "Viewer", 2: "A", 3: "B", 4: "C", 5: "Zero", 6: "NoHistory"}
    return build_season_saga(
        {"username": names[pid], "finalized": bool(winners), "rank": None,
         "signature": None, "analyticsStory": {"cards": []}},
        rows, profile_id=pid, season_start=date(2026, 9, 21), weeks_total=6,
        names=names, official_winners=winners or {}, awarded_codes=set(awarded),
    )["beats"]


@pytest.mark.parametrize("pid", [1, 2, 3])
def test_overall_podium_is_present_once_for_champion_master_and_nonwinner(pid):
    names = {1: "Champion", 2: "Master", 3: "Other"}
    rows = [
        {"profile_id": 1, "game_key": "mystery", "game_date": "2026-09-21", "score": 100},
        {"profile_id": 1, "game_key": "word", "game_date": "2026-09-23", "score": 100},
        {"profile_id": 2, "game_key": "trivia", "game_date": "2026-09-22", "score": 80},
        {"profile_id": 3, "game_key": "trivia", "game_date": "2026-09-22", "score": 50},
    ]
    winners = {
        "season_champion": [{"profile_id": 1, "username": "Champion", "points": 200}],
        "season_mystery_master": [{"profile_id": 1, "username": "Champion", "points": 100}],
        "season_wordle_master": [{"profile_id": 1, "username": "Champion", "points": 100}],
        "season_trivia_master": [{"profile_id": 2, "username": "Master", "points": 80}],
    }
    awarded = {1: ["season_champion", "season_mystery_master", "season_wordle_master"],
               2: ["season_trivia_master"], 3: []}
    beats = story(pid, rows, winners=winners, awarded=awarded[pid], names=names)
    podiums = [b for b in beats if b["kind"] == "season_podium"]
    assert len(podiums) == 1
    assert [(p["place"], p["points"]) for p in podiums[0]["visual"]["podium"]] == [(1, 200), (2, 80), (3, 50)]
    assert podiums[0]["visual"]["podium"][pid - 1]["players"][0]["you"] is True
    if pid in (1, 2):
        assert [b["kind"] for b in beats[:2]] == ["champion_opening", "season_podium"]
        assert not any(b["kind"] == "season_game_master" for b in beats)
    else:
        assert [b["kind"] for b in beats[:5]] == ["season_podium", *["season_game_master"] * 3, "welcome"]


def test_weekly_podium_is_not_limited_by_frequency_rank_and_zero_is_honest():
    rows = []
    for week in range(6):
        scores = {1: 100, 2: 90, 3: 80, 4: 70, 5: 0} if week == 0 else {1: 10, 2: 100, 3: 90, 4: 80, 5: 0}
        for pid, score in scores.items():
            rows.append({"profile_id": pid, "game_key": "trivia", "score": score,
                         "game_date": (date(2026, 9, 22) + timedelta(weeks=week)).isoformat()})
    acts = story(1, rows)
    podium = next(b["visual"] for b in acts if b["kind"] == "podium")
    assert podium["count"] == 1 and podium["frequencyRank"] == 4
    assert podium["weeks"] == [{"week": 1, "place": 1, "points": 100}]
    zero = next(b for b in story(5, rows) if b["kind"] == "podium")
    assert zero["visual"]["count"] == 0
    assert zero["visual"]["frequencyRank"] is None and zero["visual"]["weeks"] == []
    assert "kept showing up at the top" not in zero["headline"]
    assert not any(b["kind"] == "podium" for b in story(6, rows))

"""All verified personal titles share one championship opening."""
from datetime import date

import pytest

from app.badges import BADGES_BY_CODE
from app.rewind_saga import TITLE_ORDER, build_season_saga


def saga(winners, awarded):
    return build_season_saga(
        {"username": "Champion", "finalized": True, "rank": 1,
         "signature": None, "analyticsStory": {"cards": []}},
        [], profile_id=1, season_start=date(2026, 9, 21), weeks_total=6,
        names={1: "Champion", 2: "Other"}, official_winners=winners,
        awarded_codes=awarded,
    )


@pytest.mark.parametrize("count", [1, 3, 5])
def test_verified_titles_are_combined_once_with_real_badges_points_and_ties(count):
    codes = TITLE_ORDER[:count]
    winners = {code: [{"profile_id": 1, "points": (index + 1) * 100}]
               for index, code in enumerate(codes)}
    winners[codes[-1]].append({"profile_id": 2, "points": count * 100})
    result = saga(winners, set(codes) | {"brainiac"})
    beats = result["beats"]
    assert beats[0]["kind"] == "champion_opening"
    assert not any(b["kind"] in {"winner", "winner_badge", "welcome", "season_podium", "season_game_master"}
                   for b in beats)
    assert sum(b["kind"] == "champion_opening" for b in beats) == 1
    awards = beats[0]["visual"]["awards"]
    assert [a["badge"]["code"] for a in awards] == list(codes)
    assert [a["points"] for a in awards] == [(index + 1) * 100 for index in range(count)]
    assert [a["shared"] for a in awards] == [False] * (count - 1) + [True]
    for award in awards:
        badge = BADGES_BY_CODE[award["badge"]["code"]]
        assert award["badge"]["name"] == badge.name
        assert award["badge"]["rarity"] == badge.rarity
    vault = next(b for b in beats if b["kind"] == "trophy_vault")
    assert set(vault["visual"]["celebrated"]) == set(codes)
    assert len(vault["visual"]["badges"]) == count + 1
    assert [b["kind"] for b in beats[-2:]] == ["legacy", "season_two"]
    assert result["count"] == len(beats)


def test_combined_opening_still_requires_both_official_membership_and_earned_badge():
    winners = {"season_champion": [{"profile_id": 1, "points": 100}],
               "season_trivia_master": [{"profile_id": 2, "points": 90}]}
    beats = saga(winners, {"season_trivia_master"})["beats"]
    assert not any(b["kind"] == "champion_opening" for b in beats)
    actual = saga(winners, {"season_champion", "season_trivia_master"})["beats"][0]
    assert [a["badge"]["code"] for a in actual["visual"]["awards"]] == ["season_champion"]

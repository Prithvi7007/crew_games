"""Player-only Rewind benchmarks and frozen community honors."""
from datetime import date

from werkzeug.security import generate_password_hash

from app.championships import finalize_season_championships
from app.db import (
    create_profile, finalize_game_stats, get_db, get_season_for_date,
    profile_user_key, update_profile_role,
)
from app.rewind_honors import build_honors_visuals
from app.season_rewind import build_season_rewind


def player(name, role="player"):
    p = create_profile(name, generate_password_hash("test-password"), "⭐",
                       generate_password_hash("test-recovery"))
    if role != "player":
        update_profile_role(p["id"], role)
    return int(p["id"])


def score(pid, game, day, points):
    finalize_game_stats(profile_user_key(pid), game, day, points, True)


def freeze():
    season = get_season_for_date(date(2026, 10, 26))
    finalize_season_championships(season["id"], today=date(2026, 11, 2))
    return season


def comparison(recap, game="trivia"):
    act = next(b for b in recap["seasonSaga"]["beats"] if b["kind"] == "game_compare")
    return next(g for g in act["visual"]["games"] if g["key"] == game)


def state():
    db = get_db()
    return {t: [dict(row) for row in db.execute("SELECT * FROM " + t).fetchall()]
            for t in ("game_completions", "badge_awards", "season_badge_finalizations")}


def test_staff_are_excluded_from_every_game_benchmark_without_changing_results(app):
    with app.app_context():
        me = player("CohortViewer")
        a, b, c = (player(name) for name in ("CohortA", "CohortB", "CohortC"))
        admin, owner = player("CohortAdmin", "admin"), player("CohortOwner", "owner")
        for pid, values in ((me, [80, 100]), (a, [0, 100]), (b, [60]), (c, [40]),
                            (admin, [100, 100]), (owner, [100, 100])):
            for i, value in enumerate(values):
                score(pid, "trivia", ("2026-09-22", "2026-09-29")[i], value)
        season = freeze()
        before = state()
        recap = build_season_rewind(me, season)
        result = comparison(recap)
        assert result["mine"] == 90
        assert result["crew"] == 50 and result["peerPlayers"] == 3
        assert recap["insights"]["peerComparison"]["crewAverage"] == 50
        assert recap["insights"]["peerComparison"]["playersCompared"] == 3
        relative = next(c for c in recap["analyticsStory"]["cards"] if c["key"] == "relative_strength")
        assert relative["comparison"]["peers"] == 50
        assert relative["comparison"]["otherPlayers"] == 3
        standout = next(c for c in recap["analyticsStory"]["cards"] if c["key"] == "same_puzzle")
        assert standout["comparison"]["peerMedian"] == 40
        assert standout["comparison"]["peerCount"] == 3
        consistency = next(c for c in recap["analyticsStory"]["cards"] if c["key"] == "consistency")
        assert consistency["evidence"] == "The other active players' median was 1 weeks."
        # Staff can still view their own genuine scores against the player cohort.
        staff = build_season_rewind(owner, season)
        assert comparison(staff)["mine"] == 100
        assert comparison(staff)["crew"] == 60
        assert comparison(staff)["peerPlayers"] == 4
        assert recap["points"] == 180 and staff["points"] == 200
        assert state() == before


def test_staff_only_peers_do_not_create_a_crew_average_and_zero_scores_still_count(app):
    with app.app_context():
        me = player("NoPlayerPeers")
        admin = player("OnlyStaffPeer", "admin")
        score(me, "word", "2026-09-23", 80)
        score(admin, "word", "2026-09-23", 100)
        season = get_season_for_date(date(2026, 10, 26))
        recap = build_season_rewind(me, season, admin_preview=True)
        assert comparison(recap, "word")["crew"] is None
        assert comparison(recap, "word")["peerPlayers"] == 0
        zero = player("ZeroScorePeer")
        score(zero, "word", "2026-09-23", 0)
        recap = build_season_rewind(me, season, admin_preview=True)
        assert comparison(recap, "word")["crew"] == 0
        assert comparison(recap, "word")["peerPlayers"] == 1


def test_nonwinner_honors_precede_personal_story_and_winners_keep_their_reveals(app):
    with app.app_context():
        winner, other = player("HonorsWinner"), player("HonorsViewer")
        games = (("mystery", "2026-10-19"), ("trivia", "2026-10-20"),
                 ("word", "2026-10-21"), ("tick_tock", "2026-10-22"))
        for game, day in games:
            score(winner, game, day, 100)
            score(other, game, day, 10)
        season = freeze()
        before = state()
        recap = build_season_rewind(other, season)
        beats = recap["seasonSaga"]["beats"]
        assert [b["kind"] for b in beats[:6]] == [
            "season_podium", *["season_game_master"] * 4, "welcome",
        ]
        podium = beats[0]["visual"]["podium"]
        assert [(p["place"], p["points"]) for p in podium] == [(1, 400), (2, 40)]
        assert podium[1]["players"][0]["you"] is True
        masters = [b["visual"] for b in beats if b["kind"] == "season_game_master"]
        assert [m["gameKey"] for m in masters] == ["mystery", "trivia", "word", "tick_tock"]
        assert all(m["winners"][0]["name"] == "HonorsWinner" for m in masters)
        assert all(m["winners"][0]["points"] == 100 for m in masters)
        assert [b["kind"] for b in beats[-2:]] == ["legacy", "season_two"]
        champion = build_season_rewind(winner, season)
        assert champion["seasonSaga"]["beats"][0]["kind"] == "winner"
        assert not any(b["kind"] in {"season_podium", "season_game_master"}
                       for b in champion["seasonSaga"]["beats"])
        assert recap["points"] == 40 and recap["rank"] == 2
        from app.rewind_combined_preview import build_combined_preview
        actual, _ = build_combined_preview(recap, profile_id=other, season=season)
        assert actual["beats"] == beats
        demo, _ = build_combined_preview(recap, profile_id=other, season=season, selection="all")
        assert demo["beats"][0]["kind"] == "winner"
        assert not any(b["kind"] in {"season_podium", "season_game_master"} for b in demo["beats"])
        assert state() == before


def test_unfinalized_nonwinner_has_no_official_honors(app):
    with app.app_context():
        me, leader = player("DraftHonorsViewer"), player("DraftHonorsLeader")
        score(me, "trivia", "2026-10-20", 20)
        score(leader, "trivia", "2026-10-20", 80)
        season = get_season_for_date(date(2026, 10, 26))
        recap = build_season_rewind(me, season, admin_preview=True)
        assert recap["seasonSaga"]["beats"][0]["kind"] == "welcome"
        assert not any(b["kind"] in {"season_podium", "season_game_master"}
                       for b in recap["seasonSaga"]["beats"])


def test_honors_keep_all_ties_and_omit_missing_game_winners():
    winners = {
        "season_champion": [{"profile_id": 1, "username": "FrozenName", "points": 300}],
        "season_wordle_master": [
            {"profile_id": 2, "username": "TiedA", "points": 80},
            {"profile_id": 3, "username": "TiedB", "points": 80},
        ],
    }
    facts = build_honors_visuals(
        {1: 300, 2: 200, 3: 200, 4: 200, 5: 0},
        {1: "Renamed", 2: "A", 3: "B", 4: "C", 5: "Zero"},
        winners, viewer_id=4,
    )
    assert [p["place"] for p in facts["podium"]] == [1, 2]
    assert facts["podium"][0]["players"][0]["name"] == "FrozenName"
    assert len(facts["podium"][1]["players"]) == 3
    assert any(p["you"] for p in facts["podium"][1]["players"])
    assert len(facts["masters"]) == 1
    assert facts["masters"][0]["gameKey"] == "word"
    assert [w["name"] for w in facts["masters"][0]["winners"]] == ["TiedA", "TiedB"]

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_rankings_use_separate_season_and_week_filters():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")

    assert "rankings-time-filters" in source
    assert ">SEASON<" in source
    assert ">WEEK<" in source
    assert "TIME PERIOD" not in source
    assert "THE<br>BOARD." not in source

def test_rankings_keep_game_specific_filters():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")

    for label in (
        "Overall",
        "Mystery Monday",
        "Trivia Tuesday",
        "Wordle Wednesday",
        "Tick-Tock Thursday",
    ):
        assert label in source

def test_rankings_use_single_scoreboard_table():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")

    assert "rankings-leaderboard-card" in source
    assert "leader-podium" not in source
    assert "leader-me-wrap" not in source

def test_rankings_api_supports_season_and_week_query():
    source = (ROOT / "app/main/routes.py").read_text(encoding="utf-8")
    assert 'request.args.get("season", type=int)' in source
    assert 'request.args.get("week", "all")' in source

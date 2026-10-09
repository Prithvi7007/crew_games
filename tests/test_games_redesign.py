from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_games_page_lists_season_weeks_without_old_switcher():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")

    assert "games-season-weeks" in source
    assert "(data.weeks||[]).map" in source
    assert "Previous week" not in source
    assert "Next week" not in source
    assert "Four days." not in source

def test_games_page_uses_compact_rows_not_artwork_cards():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")

    assert "games-game-row" in source
    assert "v14-game-art" not in source
    assert "games-game-icon" in source

def test_games_route_builds_all_weeks_in_active_season():
    source = (ROOT / "app/main/routes.py").read_text(encoding="utf-8")
    assert 'first_monday = get_week_start(season["start_date"])' in source
    assert 'last_monday = get_week_start(season["end_date"])' in source
    assert "while monday <= last_monday" in source

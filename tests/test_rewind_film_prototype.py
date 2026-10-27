"""CREW Rewind film lab stays in preview, using real cutoff-scoped game scores."""
from datetime import date
from pathlib import Path

from app.db import create_profile, finalize_game_stats, get_season_for_date, profile_user_key
from app.season_rewind import build_season_rewind
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text()
FILM = (ROOT / "frontend/src/player/RewindFilmPrototype.jsx").read_text()
CSS = (ROOT / "frontend/src/player/styles/rewind-film.css").read_text()


def test_prototype_only_selected_on_administrator_preview_with_explicit_query():
    assert "data.rewind?.preview === true" in MAIN
    assert "get('prototype')==='1'" in MAIN
    assert "RewindFilmPrototype : pages[root.dataset.page]" in MAIN
    assert "rewind:SeasonRewind" in MAIN
    assert "/rewind?preview=1" in FILM
    assert "EXPERIMENTAL · OWNER PREVIEW" in FILM


def test_weekly_game_race_uses_real_per_game_scores_and_six_season_weeks(app):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        player = create_profile(
            "FilmTester", generate_password_hash("test-test-test"),
            "⭐", generate_password_hash("test-key"),
        )
        pid = int(player["id"])
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-09-22", 85, True)
        finalize_game_stats(profile_user_key(pid), "word", "2026-09-23", 70, True)
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-09-29", 92, True)
        data = build_season_rewind(pid, season, admin_preview=True)

    assert len(data["weeklyGameScores"]) == 6
    assert data["weeklyGameScores"][0]["games"]["trivia"] == 85
    assert data["weeklyGameScores"][0]["games"]["word"] == 70
    assert data["weeklyGameScores"][1]["games"]["trivia"] == 92
    assert data["weeklyGameScores"][2]["games"]["mystery"] == 0
    assert sum(sum(item["games"].values()) for item in data["weeklyGameScores"]) == data["points"] == 247


def test_data_drives_actual_animation_and_reduced_motion_fallback():
    assert "history.slice(0, week + 1)" in FILM
    assert "item.games?.[key] || 0" in FILM
    assert "layout={!reduce}" in FILM
    assert "setPlaying(false)" in FILM
    assert "if (!playing || reduce || phase !== 'race')" in FILM
    assert "useReducedMotion()" in FILM
    assert 'aria-label={\'Game scores through week \' ' in FILM
    assert "initial={reduce ? false" in FILM
    assert ".rewind-film-discovery" in CSS
    assert ".rewind-film-runner" in CSS

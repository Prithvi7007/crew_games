"""CREW Rewind Film Lab: score-driven visuals, permission gate, real season data."""
from datetime import date
from pathlib import Path

from app.db import create_profile, finalize_game_stats, get_season_for_date, profile_user_key
from app.season_rewind import build_season_rewind
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text()
FILM = (ROOT / "frontend/src/player/RewindFilmPrototype.jsx").read_text()
CSS = (ROOT / "frontend/src/player/styles/rewind-film.css").read_text()
ROUTE = (ROOT / "app/main/routes.py").read_text()


def test_prototype_is_server_gated_and_live_rewind_is_still_default():
    assert 'request.args.get("prototype") == "1"' in ROUTE
    assert 'user.get("role") in ("admin", "owner")' in ROUTE
    assert "if film_requested and not film_preview:" in ROUTE
    assert 'rewindFilmPrototype": film_preview' in ROUTE
    assert "data.rewindFilmPrototype === true" in MAIN
    assert "RewindFilmPrototype : pages[root.dataset.page]" in MAIN
    assert "rewind:SeasonRewind" in MAIN
    assert "/rewind?preview=1" in FILM


def test_weekly_race_uses_real_cutoff_scoped_game_scores(app):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        profile = create_profile(
            "FilmTester", generate_password_hash("test-test-test"),
            "⭐", generate_password_hash("test-key"),
        )
        pid = int(profile["id"])
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


def test_game_visuals_follow_weekly_scores_not_fake_keyframes():
    assert "history" not in FILM or "weeklyGameScores" in FILM
    assert "const weeks = recap.weeklyGameScores || []" in FILM
    assert "weeks.slice(0, limit + 1)" in FILM
    assert "Math.round((game.score/maximum)*(compact ? 252 : 600))" in FILM
    assert "rankingY[game.key]" in FILM
    assert "leadChanged ? 1650 : 1150" in FILM
    assert "const theme = GAMES[phase==='discovery' ? lead : phase==='race' ? liveLeader : null]" in FILM
    assert "leadChanges += 1" in FILM
    assert "game.score === topScore" in FILM or "item.score === topScore" in FILM
    assert "<m.path" in FILM
    assert "<m.circle" in FILM
    assert "animate={{cx:targetX,cy:targetY" in FILM
    assert "Math.round(100 * topScore / total)" in FILM
    assert "setTimeout" in FILM
    assert 'phase === "race"' not in FILM or "phase" in FILM
    assert "useReducedMotion()" in FILM
    assert "if (reduce || !weeks.length || discovery.noGames)" in FILM
    assert "aria-current={phase==='race'&&week===i?'step':undefined}" in FILM


def test_film_is_single_continuous_stage_not_a_seven_panel_dashboard():
    assert "viewBox={compact ? '0 0 430 440' : '0 0 940 480'}" in FILM
    assert 'className="rewind-film-impact"' in FILM
    assert ".rewind-film-discovery-copy .rewind-film-impact" in CSS
    assert "rewind-film-field" in FILM
    assert "rewind-film-discovery-copy" in FILM
    assert "7 CHAPTERS" not in FILM
    assert "ORIGINAL SERIES" not in FILM
    assert "rewind-film-line" not in CSS
    assert "rewind-film-timeline button" in CSS
    assert ".rewind-film-arena svg" in CSS

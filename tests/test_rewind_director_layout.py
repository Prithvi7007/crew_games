"""Director layout guards for reported duplicate metric overlays and collisions."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT/path).read_text(encoding="utf-8")


def test_one_visual_per_chapter_without_duplicate_number_overlay():
    film=source("frontend/src/player/RewindStoryFilmDirector.jsx")
    assert '<RewindDirectorScenes beat={active} recap={recap}/>' in film
    assert "rd-metric-banner" not in film
    assert "rd-ghost-number" not in film
    assert "THE NUMBER" not in film
    assert film.count('mode="wait"') == 2
    assert "rd-foot-context" not in film
    assert "rd-foot-hint" not in film


def test_methodology_stays_in_disclosure_not_chart_viewport():
    film=source("frontend/src/player/RewindStoryFilmDirector.jsx")
    scenes=source("frontend/src/player/RewindDirectorScenes.jsx")
    assert 'className="rd-evidence-panel"' in film
    assert 'className="rd-evidence-label"' in film
    assert "<p>{active.description}</p><p>{active.evidence}</p>" not in film
    assert "SCHEDULED GAME WEEKS · NOT REAL-TIME SUBMISSION ORDER" not in scenes
    assert "THE GAME THAT TILTED THE SEASON" not in scenes
    assert "rd-micro" not in scenes
    assert "rd-strength-caption" in scenes
    assert "rd-momentum-change" in scenes
    assert "rd-trajectory" in scenes


def test_charts_and_captions_have_responsive_flow():
    css=source("app/static/css/rewind-director.css")
    assert "Director composition: data labels sit in flow" in css
    assert ".rd-visual-shell{max-width:100%" in css
    assert ".rd-footbar{min-height:clamp(61px,8dvh,83px);justify-content:center" in css
    assert ".rd-trajectory svg{max-height:clamp(145px,25dvh,215px)}" in css
    assert ".rd-strength-caption" in css
    assert ".rd-momentum-change" in css
    assert "prefers-reduced-motion:reduce" in css


def test_weekly_bars_use_real_games_completed_not_the_player_rank():
    scene=source("frontend/src/player/RewindDirectorScenes.jsx")
    assert "const max=Math.max(1,...weeks.map(w=>Number(w.played)||0))" in scene
    assert "<strong>{w.played||'–'}</strong>" in scene

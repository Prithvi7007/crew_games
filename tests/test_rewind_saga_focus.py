"""Focused Rewind Act 4/5 — reduce cognitive load without changing score evidence."""
from datetime import date
from pathlib import Path

from app.rewind_saga import build_season_saga

ROOT=Path(__file__).resolve().parents[1]
def source(path):
    return (ROOT/path).read_text(encoding="utf-8")

def test_score_comparison_reveals_one_game_at_a_time_and_waits_for_all_four():
    scene=source("frontend/src/player/RewindSagaScene.jsx")
    film=source("frontend/src/player/RewindPlayerCinema.jsx")
    css=source("app/static/css/rewind-saga.css")
    assert "function Compare({games, reduce, playing})" in scene
    assert "saga-spotlight-stage" in scene
    assert "AnimatePresence mode=\"wait\" initial={false}" in scene
    assert "setStep(current=>Math.min(current+1,shown.length-1))" in scene
    assert "window.clearInterval(timer)" in scene
    assert "aria-pressed={step===i}" in scene
    assert "role=\"group\" aria-label=\"Choose game comparison\"" in scene
    assert "playing={playing}" in film
    assert "game_compare" in film and "3800" in film
    assert ".saga-spotlight-pick:focus-visible" in css
    assert ".saga-spotlight-stage" in css
    assert ".saga-comparisons{" not in css
    assert "className=\"saga-comparison\"" not in scene

def test_points_mix_is_single_bar_with_no_participation_chart():
    scene=source("frontend/src/player/RewindSagaScene.jsx")
    engine=source("app/rewind_saga.py")
    css=source("app/static/css/rewind-saga.css")
    assert 'className="saga-dna-focus-bar"' in scene
    assert "g.pointShare" in scene
    assert "g.gameShare" not in scene
    assert "YOUR GAME MIX" not in scene
    assert ".saga-dna-focus-bar" in css
    assert ".saga-dna{" not in css
    assert "No participation comparison is shown." in engine
    assert "if all_points[me] > 0:" in engine

def test_sparse_player_does_not_receive_fabricated_points_breakdown():
    recap={"username":"Sparse","finalized":False,"rank":None,
           "signature":None,"analyticsStory":{"cards":[]}}
    rows=[
        {"profile_id":1,"game_key":"word","game_date":"2026-09-23","score":0},
        {"profile_id":2,"game_key":"trivia","game_date":"2026-09-22","score":90},
    ]
    saga=build_season_saga(recap,rows,profile_id=1,season_start=date(2026,9,21),
                            weeks_total=6,names={1:"Sparse",2:"Peer"},
                            official_winners={},awarded_codes=set())
    kinds=[beat["kind"] for beat in saga["beats"]]
    assert "game_compare" in kinds
    assert "game_dna" not in kinds
    comparison=next(beat["visual"]["games"] for beat in saga["beats"]
                    if beat["kind"]=="game_compare")
    word=next(item for item in comparison if item["key"]=="word")
    assert word["mine"]==0
    assert word["crew"] is None

def test_real_points_mix_still_reconciles_four_games_and_benchmark():
    recap={"username":"Focused","finalized":False,"rank":1,
           "signature":None,"analyticsStory":{"cards":[]}}
    rows=[
        {"profile_id":1,"game_key":"mystery","game_date":"2026-09-21","score":60},
        {"profile_id":1,"game_key":"trivia","game_date":"2026-09-22","score":80},
        {"profile_id":1,"game_key":"word","game_date":"2026-09-23","score":40},
        {"profile_id":1,"game_key":"tick_tock","game_date":"2026-09-24","score":20},
        {"profile_id":2,"game_key":"trivia","game_date":"2026-09-22","score":100},
    ]
    saga=build_season_saga(recap,rows,profile_id=1,season_start=date(2026,9,21),
                            weeks_total=6,names={1:"Focused",2:"Peer"},
                            official_winners={},awarded_codes=set())
    points=next(beat for beat in saga["beats"] if beat["kind"]=="game_dna")
    assert points["visual"]["totalPoints"]==200
    shares={g["key"]:g["pointShare"] for g in points["visual"]["games"]}
    assert shares=={"mystery":30,"trivia":40,"word":20,"tick_tock":10}
    assert points["evidence"].startswith("Points share:")

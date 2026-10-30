"""Regression: cinematic game comparison must import every React primitive used.

The preceding build transformed JSX but did not flag unresolved JS identifiers,
which resulted in a black screen at the comparison chapter in the browser.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_game_comparison_runtime_dependencies_are_imported():
    saga = (ROOT / "frontend/src/player/RewindSagaScene.jsx").read_text(
        encoding="utf-8"
    )
    assert "import React, {useEffect, useState} from 'react';" in saga
    assert "import {AnimatePresence, m} from 'motion/react';" in saga
    assert "function Compare({games, reduce, playing})" in saga
    assert "const [step,setStep]=useState(0)" in saga
    assert "useEffect(()=>{" in saga
    assert '<AnimatePresence mode="wait" initial={false}>' in saga


def test_comparison_chapter_is_still_wired_in_the_film():
    cinema = (ROOT / "frontend/src/player/RewindPlayerCinema.jsx").read_text(
        encoding="utf-8"
    )
    assert "game_compare" in cinema
    assert "3800" in cinema
    assert "<RewindSagaScene beat={scene} recap={recap} reduce={reduce} playing={playing}/>" in cinema

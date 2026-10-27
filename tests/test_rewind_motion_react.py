"""CREW Rewind uses Motion for React only, with respectful scene transitions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
LOCK = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
REWIND = (ROOT / "frontend/src/player/SeasonRewind.jsx").read_text(encoding="utf-8")
NATIVE = (ROOT / "frontend/src/player/CrewMotion.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/player/styles/rewind.css").read_text(encoding="utf-8")


def test_motion_dependency_is_pinned_in_manifest_and_lockfile():
    assert PACKAGE["dependencies"]["motion"] == "14.6.0"
    assert LOCK["packages"][""]["dependencies"]["motion"] == "14.6.0"
    packages = LOCK["packages"]
    for name in ("motion", "framer-motion", "motion-dom", "motion-utils"):
        assert packages["node_modules/" + name]["version"] == "14.6.0"
    assert packages["node_modules/tslib"]["version"].startswith("2.")
    assert packages["node_modules/motion"]["dependencies"]["framer-motion"] == "14.6.0"


def test_rewind_is_only_new_motion_react_consumer():
    assert "from 'motion/react'" in REWIND
    assert "from 'motion/react'" not in NATIVE
    assert "<LazyMotion features={domAnimation} strict>" in REWIND
    assert '<MotionConfig reducedMotion="user">' in REWIND
    assert '<AnimatePresence mode="wait" initial={false} custom={direction}>' in REWIND
    assert 'variants={SCENE_VARIANTS}' in REWIND
    assert 'initial={reduceMotion ? false : \'enter\'}' in REWIND
    assert 'exit={reduceMotion ? undefined : \'exit\'}' in REWIND


def test_scene_is_accessible_and_not_css_animated_twice():
    assert "onTouchEnd={event =>" in REWIND
    assert "if (Math.abs(delta) > 65) next(delta < 0 ? 1 : -1)" in REWIND
    assert 'role="status" aria-live="polite" aria-atomic="true"' in REWIND
    assert "if (step === last)" in REWIND
    assert "onClick={shareHighlights}" in REWIND
    assert "animation: rewind-scene-enter" not in CSS
    assert ".rewind-scene { flex: 1; display: flex; flex-direction: column; }" in CSS


def test_achievement_reveals_preserve_meaningful_data():
    for text in ("recap.points", "recap.gamesPlayed", "recap.badges?.count", "recap.rank"):
        assert text in REWIND
    assert "<BadgeMedallion badge={trophy} size=\"normal\" seasonNumber={1}/>" in REWIND
    assert "initial={revealStart}" in REWIND
    assert "transition={revealTransition}" in REWIND
    assert "reduceMotion ? {duration: 0}" in REWIND

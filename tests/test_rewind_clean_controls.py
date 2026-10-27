"""Rewind story controls must be thin without sacrificing accessible touch targets."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend/src/player/styles/rewind.css").read_text(encoding="utf-8")
JSX = (ROOT / "frontend/src/player/SeasonRewind.jsx").read_text(encoding="utf-8")
FOUNDATION = (ROOT / "app/static/css/phase1-foundation.css").read_text(encoding="utf-8")


def _rules(selector):
    pattern = rf"(?<![\w.-]){re.escape(selector)}\s*\{{([^}}]+)\}}"
    matches = re.findall(pattern, CSS)
    assert matches, f"Expected a rule for {selector}"
    # The base selector occurs first; narrow mobile overrides only change spacing.
    return dict((key.strip(), value.strip()) for key, value in re.findall(
        r"([\w-]+)\s*:\s*([^;]+);", matches[0]
    ))


def test_progress_buttons_are_tappable_but_visually_thin():
    # CREW's global accessibility rule enforces 44px minimum controls.
    assert "min-height: var(--crew-tap-target)" in FOUNDATION
    container = _rules(".rewind-progress")
    target = _rules(".rewind-progress button")
    bar = _rules(".rewind-progress button::before")
    seen = _rules(".rewind-progress button.is-seen::before")

    assert container["height"] == "44px"
    assert target["height"] == "44px"
    assert target["min-height"] == "44px"
    assert target["background"] == "transparent"
    assert target["position"] == "relative"
    assert bar["height"] == "4px"
    assert bar["position"] == "absolute"
    assert bar["top"] == "50%"
    assert bar["border-radius"] == "var(--crew-radius-pill, 999px)"
    assert seen["background"] == "var(--rewind-blue)"
    assert "background" not in target or target["background"] == "transparent"


def test_progress_keeps_seven_interactive_accessible_story_steps():
    assert "PAGES.map((item, index) => <button" in JSX
    assert "aria-label={'Go to story ' + (index + 1)}" in JSX
    assert "aria-current={index === step ? 'step' : undefined}" in JSX
    assert "onClick={() => { setDirection(index < step ? -1 : 1); setStep(index); setFeedback(''); }}" in JSX
    assert ".rewind-progress button:focus-visible" in CSS or (
        ".crew-rewind button:focus-visible" in CSS
    )


def test_no_large_asterisk_or_decorative_rings_cover_final_card():
    assert "rewind-orbit" not in JSX
    assert ".rewind-orbit" not in CSS
    assert ".rewind-stage::before" not in CSS
    assert "rewind-tone-finale" in CSS
    assert "className=\"rewind-scene\"" in JSX

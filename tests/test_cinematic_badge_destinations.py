"""Navigation and keyboard contracts for newly earned cinematic badges."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "frontend" / "src" / "player"


def test_live_cinematic_offers_results_and_earned_badges():
    cinematic = (ROOT / "BadgeUnlockPreview.jsx").read_text(encoding="utf-8")

    # The saved-award cinema exposes both next steps. The staff lab does not
    # claim preview badges as actual awards or navigate to a player's collection.
    assert "onClick={onDismiss || skip}" in cinematic
    assert "onDismiss ? 'View Results' : 'Skip animation'" in cinematic
    assert '{onDismiss ? <a className="cul-view-badges" href="/trophies">' in cinematic
    assert 'View My Badges <span aria-hidden="true">↗</span>' in cinematic


def test_both_destinations_are_keyboard_reachable_and_screen_fitted():
    cinematic = (ROOT / "BadgeUnlockPreview.jsx").read_text(encoding="utf-8")
    css = (ROOT / "styles" / "badge-unlock-preview.css").read_text(encoding="utf-8")
    browser = (ROOT.parents[2] / "tests" / "test_browser_smoke.py").read_text(
        encoding="utf-8"
    )

    assert "querySelectorAll('button:not([disabled]), a[href]')" in cinematic
    assert "event.shiftKey" in cinematic
    assert "event.key === 'Escape'" in cinematic
    assert "previousFocus?.focus?.()" in cinematic
    assert ".cul-live .cul-cinema-footer a.cul-view-badges" in css
    assert ".cul-live .cul-cinema-actions" in css
    assert 'badgesTop: badges.top, badgesBottom: badges.bottom' in browser
    assert 'name="View My Badges"' in browser
    assert 'name="View Results"' in browser

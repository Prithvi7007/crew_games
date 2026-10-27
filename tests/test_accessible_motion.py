"""Accessible, progressive motion for CREW's authenticated React experience.

No animated element may require Web Animations to become visible: native
animations are optional polish, not a dependency for gameplay/navigation.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOTION = (ROOT / "frontend/src/player/CrewMotion.js").read_text(encoding="utf-8")
PLAYER = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
REWIND = (ROOT / "frontend/src/player/SeasonRewind.jsx").read_text(encoding="utf-8")
STYLE = (ROOT / "frontend/src/player/styles/rewind.css").read_text(encoding="utf-8")


def test_page_entrances_use_native_motion_with_safe_fallbacks():
    assert "enableCrewEntranceMotion" in MOTION
    assert "enableCrewEntranceMotion(document.getElementById('crew-player-root'))" in PLAYER
    assert "window.IntersectionObserver" in MOTION
    assert "Element.prototype.animate" in MOTION
    assert "media?.matches" in MOTION
    assert "if (!root" in MOTION
    assert "document.visibilityState === 'hidden'" in MOTION
    assert "getClientRects().length > 0" in MOTION
    assert "root.querySelectorAll(CREW_ENTRANCE_SELECTOR)" in MOTION
    assert "opacity: 1" in MOTION
    assert "fill: 'none'" in MOTION
    assert "delay = Math.min(index % 4, 3) * 35" in MOTION
    assert "duration: 360" in MOTION


def test_accessible_motion_cleans_up_and_reacts_to_setting_changes():
    assert "media?.addEventListener?.('change', onPreferenceChange)" in MOTION
    assert "media?.removeEventListener?.('change', onPreferenceChange)" in MOTION
    assert "observer.disconnect()" in MOTION
    assert "handle.cancel()" in MOTION
    assert "return () => {" in MOTION
    assert "new WeakSet()" in MOTION
    assert "animated.add(entry.target)" in MOTION


def test_entrance_targets_exclude_gameplay_and_user_controls():
    section = MOTION.split("export const CREW_ENTRANCE_SELECTOR =", 1)[1].split("].join(", 1)[0]
    for place in (
        ".v17-intro.home-summary",
        ".games-week-block",
        ".rankings-head",
        ".v20-profile-hero",
        ".trophy-hero",
    ):
        assert place in section
    for forbidden in (
        "react-trivia-option", "word-key", "crew-result-stage",
        "button", "dialog", "trophy-tour",
    ):
        assert forbidden not in section


def test_rewind_has_directional_transitions_and_reduced_motion_exit():
    assert "const [direction, setDirection] = useState(1)" in REWIND
    assert "setDirection(index < step ? -1 : 1)" in REWIND
    assert "'--rewind-shift': direction < 0 ? '-14px' : '14px'" in REWIND
    assert 'role="status" aria-live="polite" aria-atomic="true"' in REWIND
    assert "rewind-scene-enter 360ms" in STYLE
    assert "translate3d(var(--rewind-shift, 14px),0,0)" in STYLE
    assert re.search(
        r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{"
        r"[^}]*\.rewind-scene\s*\{\s*animation:\s*none",
        STYLE,
        re.S,
    )
    assert "animation-iteration-count: infinite" not in STYLE

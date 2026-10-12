"""The trophy tour should be an immersive, accessible badge-design walkthrough.

These contracts guard against bringing back a framed modal or rarity-only step.
They exercise the shipped component/CSS and preserve private award semantics.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOUR = ROOT / "frontend/src/player/TrophyWelcomeTour.jsx"
STYLES = ROOT / "frontend/src/player/styles/trophy-tour.css"


def test_unboxed_blurred_overlay_does_not_use_card_surface():
    css = STYLES.read_text(encoding="utf-8")
    assert "backdrop-filter:blur(22px) saturate(.72)" in css
    assert "-webkit-backdrop-filter:blur(22px) saturate(.72)" in css
    assert ".crew-tour-dialog{\n  width:100%;max-width:none;height:100dvh;max-height:100dvh;" in css
    assert "border:0;border-radius:0;background:transparent;box-shadow:none;" in css
    assert ".crew-tour-dialog::before{display:none}" in css
    assert ".crew-tour-vault{\n  width:min(100%,700px);height:275px;" in css
    assert "border:0;border-radius:0;background:transparent;box-shadow:none;" in css


def test_anatomy_reveals_standalone_medal_layers_sequentially():
    source = TOUR.read_text(encoding="utf-8")
    css = STYLES.read_text(encoding="utf-8")
    assert "Anatomy of a CREW badge" in source
    assert "Watch the medal come together, one detail at a time." in source
    assert "const ANATOMY_PHASES" in source
    for label in ("RARITY FRAME", "GAME SIGNATURE", "ACHIEVEMENT EMBLEM",
                  "SEASON STAMP", "COMPLETE MEDAL"):
        assert label in source
    assert "YOUR AVATAR" not in source
    anatomy = source.split('{step === 1 ?', 1)[1].split('{step === 2 ?', 1)[0]
    assert "BadgeMedallion" in anatomy
    assert "EquippedProfileBadge" not in anatomy
    assert "avatar=" not in anatomy
    assert "crew-tour-medal-build" in anatomy
    assert "data-phase={anatomyPhase}" in anatomy
    assert "aria-live=\"polite\"" in anatomy
    assert "Replay reveal" in anatomy
    assert "2400" in source
    assert "window.clearInterval(interval)" in source
    for phase in range(5):
        assert f'[data-phase="{phase}"]' in css
    assert "@keyframes crew-tour-rarity-cycle" in css
    assert ".crew-tour-medal-build .medallion-inner" in css
    assert ".crew-tour-medal-build .crew-insignia" in css
    assert ".crew-tour-medal-season" in css


def test_final_step_demonstrates_equipped_avatar_without_fake_awards():
    source = TOUR.read_text(encoding="utf-8")
    assert 'className="crew-tour-wearing"' in source
    assert "preview: !earned.length" in source
    assert "Your earned badge, ready to wear." in source
    assert "Preview of how a future achievement" in source
    assert "tour.earnedCount" in source
    assert "earned.length ? 'These are real achievements" in source
    assert "if (tour.preview) { onClose(); return; }" in source


def test_responsive_unboxed_tour_preserves_focus_and_reduced_motion():
    css = STYLES.read_text(encoding="utf-8")
    source = TOUR.read_text(encoding="utf-8")
    assert "@media(max-width:690px)" in css
    assert ".crew-tour-medal-guide" in css
    assert "@media(max-width:480px)" in css
    assert ".crew-tour-dialog{\n    justify-content:flex-start;" in css
    assert ".crew-tour-medal-build{width:min(54vw,215px)}" in css
    assert "overscroll-behavior:contain" in css
    assert ".crew-tour-close:focus-visible" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
    assert ".crew-tour-medal-narration{animation:none!important;transition:none!important}" in css
    assert 'role="dialog" aria-modal="true"' in source
    assert "dialogRef.current?.focus()" in source
    assert "function handleKeys(event)" in source
    assert "document.body.style.overflow = 'hidden'" in source

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
    assert "How a badge works" in source
    assert "Built one detail at a time." not in source
    assert "const ANATOMY_PHASES" in source
    for label in ("RARITY FRAME", "GAME SIGNATURE", "ACHIEVEMENT EMBLEM",
                  "SEASON STAMP", "COMPLETE BADGE"):
        assert label in source
    assert "YOUR AVATAR" not in source
    anatomy = source.split('{step === 1 ?', 1)[1].split('{step === 2 ?', 1)[0]
    assert "BadgeMedallion" in anatomy
    assert "EquippedProfileBadge" not in anatomy
    assert "avatar=" not in anatomy
    assert "crew-tour-medal-build" in anatomy
    assert "data-phase={anatomyPhase}" in anatomy
    assert "aria-live=\"polite\"" in anatomy
    assert "Replay badge" in anatomy
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
    assert 'className="crew-tour-wear-scene" key={wearReplay}' in source
    assert "preview: !earned.length" in source
    assert "Your badge, your profile." in source
    assert "Preview: your future badge." in source
    assert "tour.earnedCount" in source
    assert "earned.length ? 'Badges you have earned so far." in source
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

def test_wear_badge_before_after_animation_has_replay_and_accessible_fallback():
    component = TOUR.read_text(encoding="utf-8")
    css = STYLES.read_text(encoding="utf-8")
    stage = component.split('{step === 3 ?', 1)[1].split('} : null}', 1)[0]
    assert 'crew-tour-wear-before' in stage
    assert 'crew-tour-wear-plain' in stage
    assert 'crew-tour-wear-after' in stage
    assert 'EquippedProfileBadge' in stage
    assert 'avatar={avatar ||' in stage
    assert 'key={wearReplay}' in stage
    assert 'setWearReplay(value => value + 1)' in stage
    assert 'Your profile changes from a plain avatar' in stage
    assert "preview: !earned.length" in stage
    for part in ('@keyframes crew-wear-before', '@keyframes crew-wear-after',
                 '@keyframes crew-wear-ring', '@keyframes crew-wear-game-ring',
                 '@keyframes crew-wear-mark', '@keyframes crew-wear-season',
                 '@keyframes crew-wear-flash'):
        assert part in css
    assert '.crew-tour-wear-before{display:none}' in css
    assert '.crew-tour-wear-after{opacity:1}' in css
    assert '@media(max-width:480px)' in css

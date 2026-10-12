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


def test_design_step_explains_every_badge_layer_not_only_rarity():
    source = TOUR.read_text(encoding="utf-8")
    assert "Anatomy of a CREW badge" in source
    assert "five deliberate layers" not in source  # Copy remains conversational.
    assert "Five deliberate layers" in source
    assert "EquippedProfileBadge" in source
    assert "crew-tour-anatomy" in source
    for label in ("RARITY FRAME", "GAME SIGNATURE", "ACHIEVEMENT MARK",
                  "SEASON STAMP", "YOUR AVATAR"):
        assert label in source
    assert "outer metal signals Common, Rare, Epic or Legendary" in source
    assert "colored inner ring identifies which CREW game" in source
    assert "upper-right symbol celebrates the exact milestone" in source
    assert "lower-right S-number records the season" in source
    assert "The player stays at the center" in source
    assert "Illustrative example · not an earned award" in source
    assert "<EquippedProfileBadge badge={{ ...badgeFromAwardCode('case_closed')" in source
    assert 'className="crew-tour-tiers"' not in source


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
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "@media(max-width:480px)" in css
    assert ".crew-tour-dialog{\n    justify-content:flex-start;" in css
    assert ".crew-tour-anatomy-avatar .crew-equipped-badge{width:159px;height:159px;" in css
    assert "overscroll-behavior:contain" in css
    assert ".crew-tour-close:focus-visible" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
    assert ".crew-tour-anatomy-rarities{animation:none!important;transition:none!important}" in css
    assert 'role="dialog" aria-modal="true"' in source
    assert "dialogRef.current?.focus()" in source
    assert "function handleKeys(event)" in source
    assert "document.body.style.overflow = 'hidden'" in source

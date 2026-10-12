"""Opening-scene regression: an unmistakable trophy vault reveal.

The animation is CSS-owned and decorative so gameplay, keyboard focus,
reduced-motion preferences and the October 19 public gate remain unaffected.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOUR = ROOT / "frontend/src/player/TrophyWelcomeTour.jsx"
STYLES = ROOT / "frontend/src/player/styles/trophy-tour.css"


def test_first_welcome_step_has_full_vault_opening_scene():
    source = TOUR.read_text(encoding="utf-8")
    assert 'step === 0 ? <div className="crew-tour-vault" aria-hidden="true">' in source
    assert 'className="crew-tour-vault-door is-left"' in source
    assert 'className="crew-tour-vault-door is-right"' in source
    assert 'className="crew-tour-vault-trophy"' in source
    assert 'className="crew-tour-vault-halo is-outer"' in source
    assert 'className="crew-tour-vault-halo is-middle"' in source
    assert 'className="crew-tour-vault-halo is-inner"' in source
    assert "VAULT ACCESS GRANTED" in source
    assert '<BadgeMedallion badge={badgeFromAwardCode("badge_hunter")} size="victory"/>' in source
    # Animation must not falsely represent unearned achievements as the user's trophies.
    assert "earned.length ? 'These are real achievements" in source
    assert "tour.earnedCount" in source


def test_vault_sequence_animates_beyond_subtle_dialog_and_two_stars():
    source = STYLES.read_text(encoding="utf-8")
    for keyframe in (
        "@keyframes crew-vault-door-left",
        "@keyframes crew-vault-door-right",
        "@keyframes crew-vault-ring",
        "@keyframes crew-vault-medal",
        "@keyframes crew-vault-ignite",
        "@keyframes crew-vault-status",
        "@keyframes crew-vault-flare",
    ):
        assert keyframe in source
    assert ".crew-tour-vault-door.is-left{animation:" in source
    assert ".crew-tour-vault-door.is-right{animation:" in source
    assert ".crew-tour-vault-trophy{animation:" in source
    assert ".crew-tour-vault-status{animation:" in source
    assert ".crew-tour-vault-halo.is-inner{animation:" in source
    # Scene should remain open after the animated doors clear the frame.
    assert "100%{transform:translateX(-106%)}" in source
    assert "100%{transform:translateX(106%)}" in source
    assert "both}" in source


def test_vault_has_reduced_motion_static_final_frame_and_mobile_layout():
    source = STYLES.read_text(encoding="utf-8")
    assert "@media(max-width:480px)" in source
    assert ".crew-tour-vault{height:178px;" in source
    assert "@media(prefers-reduced-motion:reduce)" in source
    assert ".crew-tour-vault-trophy .trophy-medallion-victory" in source
    assert "animation:none!important;transition:none!important;" in source
    assert ".crew-tour-vault-door.is-left{" in source
    assert "left:0;transform:translateX(-106%);" in source
    assert "right:0;transform:translateX(106%);" in source
    tour = TOUR.read_text(encoding="utf-8")
    assert 'role="dialog" aria-modal="true"' in tour
    assert "dialogRef.current?.focus()" in tour
    assert "function handleKeys(event)" in tour
    assert "if (tour.preview) { onClose(); return; }" in tour

"""Trophy polish contracts: rarity art, visible trophy identities, and real award reveals.

These static checks complement the full backend award integration suite and
the production React build.
"""
import re
from pathlib import Path

from app.badges import BADGES

ROOT = Path(__file__).resolve().parents[1]
TROPHIES = ROOT / "frontend/src/player/TrophyRoom.jsx"
APP = ROOT / "frontend/src/player/main.jsx"
CSS = ROOT / "frontend/src/player/styles/trophies.css"


def test_result_award_catalog_exactly_matches_server_definitions():
    source = TROPHIES.read_text(encoding="utf-8")
    part = source.split("export const BADGE_CATALOG = Object.freeze({", 1)[1].split("});", 1)[0]
    definitions = {
        code: (name, rarity, game_key)
        for code, name, rarity, game_key in re.findall(
            r"^\s*(\w+): \['([^']+)', '(common|rare|epic|legendary)', (null|'[^']+')\],?$",
            part, re.M,
        )
    }
    normalized = {
        code: (name, rarity, game_key.strip("'") if game_key != "null" else None)
        for code, (name, rarity, game_key) in definitions.items()
    }
    assert normalized == {
        badge.code: (badge.name, badge.rarity, badge.game_key) for badge in BADGES
    }
    assert "Object.prototype.hasOwnProperty.call(BADGE_CATALOG, code)" in source


def test_locked_badges_reveal_identity_and_artwork():
    source = TROPHIES.read_text(encoding="utf-8")
    assert "const hidden = false;" in source
    assert "concealed={hidden}" in source
    assert "hidden ? 'Undiscovered achievement' : badge.name" in source
    assert "badge.earned" in source


def test_rarity_is_distinct_without_changing_mobile_card_dimensions():
    css = CSS.read_text(encoding="utf-8")
    for rarity in ("common", "rare", "epic", "legendary"):
        assert f".trophy-badge-card.trophy-rarity-{rarity}" in css
    assert "var(--rarity-edge)" in css
    assert "var(--rarity-halo)" in css
    assert ".trophy-badge-card.is-mysterious" in css
    assert ".trophy-badge-card {min-height:302px;padding:12px 10px;}" in css


def test_game_result_celebrates_only_new_server_awards():
    source = APP.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "function BadgeUnlockCelebration({ codes=[] })" in source
    assert "const medals = [...new Set(codes)].map(badgeFromAwardCode).filter(Boolean)" in source
    assert "<BadgeUnlockCelebration codes={badges}/>" in source
    assert "<BadgeMedallion badge={featured} size=\"victory\"/>" in source
    assert "onClick={() => setDismissed(true)}" in source
    assert "href=\"/trophies\"" in source
    assert "aria-label=\"Newly earned badges\"" in source
    assert "@keyframes crew-trophy-reveal" in css
    assert "@media (prefers-reduced-motion:reduce)" in css

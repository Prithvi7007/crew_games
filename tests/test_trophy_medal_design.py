"""Guard the single visual grammar used by all collectible CREW badges.

The ring encodes rarity outside and game identity inside. The center is one
high-contrast icon; these assertions intentionally don't change award rules.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TROPHIES = ROOT / "frontend/src/player/TrophyRoom.jsx"
STYLES = ROOT / "frontend/src/player/styles/trophies.css"


def source():
    return TROPHIES.read_text(encoding="utf-8")


def test_all_catalog_badges_have_unique_clean_insignias():
    text = source()
    motifs = text.split("const MOTIFS = Object.freeze({", 1)[1].split("});", 1)[0]
    catalog = text.split("export const BADGE_CATALOG = Object.freeze({", 1)[1].split("});", 1)[0]
    codes = re.findall(r"^  ([a-z_]+): '([^']+)',", motifs, re.MULTILINE)
    catalog_codes = re.findall(r"^  ([a-z_]+): \[", catalog, re.MULTILINE)
    assert len(codes) == len(catalog_codes) == 21
    assert {name for name, _ in codes} == set(catalog_codes)
    assert len({path for _, path in codes}) == len(codes)
    assert "INSIGNIA_DETAILS" not in text
    assert "crew-insignia-shadow" not in text
    assert "crew-insignia-engraving" not in text
    assert "crew-insignia-halo" not in text


def test_color_encoding_keeps_rarity_and_game_separate():
    text = source()
    css = STYLES.read_text(encoding="utf-8")
    assert "return [[focus, .5]" in text
    assert "[key, 1/6]" in text
    assert "return GAME_ORDER.map(key => [key, .25])" in text
    assert "if (badge.gameKey && GAME_COLORS[badge.gameKey]) return [[badge.gameKey, 1]]" in text
    assert "stroke={GAME_COLORS[key]}" in text
    assert "stroke:var(--rarity-ring)" in css
    assert "stroke:var(--insignia-color,var(--badge-accent))" in css
    assert "style={{ '--insignia-color': insigniaColor(badge) }}" in text


def test_one_art_system_in_collection_and_avatar():
    text = source()
    assert text.count("<Insignia badge={badge}") == 2
    assert "crew-equipped-achievement" in text
    assert "GameIdentityRing badge={badge}" in text
    assert "crew-insignia-jewel" not in text
    assert "trophy-aura-flare trophy-aura-flare-left" not in text

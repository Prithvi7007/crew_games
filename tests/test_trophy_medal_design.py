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


def test_compact_avatar_emphasizes_real_achievement_without_changing_badge_identity():
    text = source()
    css = STYLES.read_text(encoding="utf-8")

    # The same 21 vector motifs belong to medals and equipped avatar satellites.
    assert "<Insignia badge={badge} compact/>" in text
    assert "viewBox={size === 'compact' ? '16 16 68 68' : '0 0 100 100'}" in text
    assert '<GameIdentityRing badge={badge} radius={39} className="crew-equipped-game-ring"/>' in text
    assert "S{String(badge.seasonNumber).padStart(2, '0')}" in text

    # The small satellite must be large enough to show its real line-art emblem.
    compact = re.search(
        r"\.crew-equipped-badge\.is-compact \.crew-equipped-achievement\s*\{([^}]*)\}", css
    )
    assert compact is not None
    width = re.search(r"width:\s*(\d+)%", compact.group(1))
    assert width is not None and int(width.group(1)) >= 40


def test_equipped_badge_hover_identifies_the_real_award():
    text = source()
    component = text.split('export function EquippedProfileBadge(', 1)[1].split('function BadgeCard(', 1)[0]
    # The same badge payload identifies a profile or leaderboard badge on hover.
    assert 'title={tooltipLabel}' in component
    assert "[badge.name, rarityLabel, seasonStamp, badge.preview ? 'Private preview' : null]" in component
    assert "badge.rarity.charAt(0).toUpperCase()" in component
    assert "String(badge.seasonNumber).padStart(2, '0')" in component
    assert 'role="img" aria-label={badge.name' in component
    assert '<Insignia badge={badge} compact/>' in component

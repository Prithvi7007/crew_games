"""The collection retains all 21 awards in compact, inspectable groups."""
from pathlib import Path
import re

from app.badges import BADGES

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "frontend/src/player/TrophyRoom.jsx"
STYLES = ROOT / "frontend/src/player/styles/trophies.css"

SECTION_CATALOG = (
    ("mystery", "Mystery Monday", "game_mastery", "mystery", 3),
    ("trivia", "Trivia Tuesday", "game_mastery", "trivia", 3),
    ("word", "Wordle Wednesday", "game_mastery", "word", 3),
    ("tick_tock", "Tick-Tock Thursday", "game_mastery", "tick_tock", 3),
    ("leaderboard", "Rivalry & Rankings", "leaderboard", None, 6),
    ("collection", "Collection Milestones", "collection", None, 2),
    ("secret", "Secret Achievements", "secret", None, 1),
)


def test_every_achievement_belongs_to_one_named_group():
    source = COMPONENT.read_text(encoding="utf-8")
    meta = source.split("const BADGE_SECTIONS = [", 1)[1].split("];", 1)[0]
    for key, title, vertical, game_key, expected in SECTION_CATALOG:
        assert f"key: '{key}', title: '{title}'" in meta
        assert f"vertical: '{vertical}'" in meta
        if game_key:
            assert f"gameKey: '{game_key}'" in meta
        found = [badge for badge in BADGES if badge.vertical == vertical
                 and (game_key is None or badge.game_key == game_key)]
        assert len(found) == expected
    grouped = [
        (badge.code, key)
        for key, _, vertical, game_key, _ in SECTION_CATALOG
        for badge in BADGES
        if badge.vertical == vertical and (game_key is None or badge.game_key == game_key)
    ]
    assert len(grouped) == len(BADGES) == 21
    assert len({code for code, _ in grouped}) == len(BADGES)


def test_groups_are_paths_with_one_detail_area_and_small_screen_browsing():
    source = COMPONENT.read_text(encoding="utf-8")
    css = STYLES.read_text(encoding="utf-8")
    assert 'badgeSections.map(group => <section className="trophy-path-section"' in source
    assert "aria-labelledby={'trophy-group-'+group.key}" in source
    assert 'className="trophy-group-heading"' in source
    assert "group.badges.filter(badge => badge.earned).length" in source
    assert 'className="trophy-path-list"' in source
    assert source.count('id="trophy-badge-detail"') == 1
    assert "filtered.filter(badge => badge.vertical === group.vertical" in source
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in css
    assert "overflow-x:auto" in css
    assert "scroll-snap-type:x proximity" in css
    assert "@media(max-width:600px)" in css


def test_filters_and_try_on_work_across_all_sections():
    source = COMPONENT.read_text(encoding="utf-8")
    assert "filter === 'all' ? badges : badges.filter" in source
    assert "BADGE_SECTIONS.map(group =>" in source
    assert "onSelect={inspectBadge}" in source
    assert "previewMode={previewMode}" in source
    assert "isEquipped={previewMode ? previewCode === badge.code" in source
    assert "filtered.find(badge => badge.code === selectedCode)" in source
    assert "|| filtered[0]" in source
    assert 'name="collection" value={filter}' in source
    assert 'Preview tools' in source
    assert "role=\"status\" aria-live=\"polite\"" in source


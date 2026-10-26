"""Meaningful contrast and completeness checks for seven CREW Rewind scenes."""
import re
from pathlib import Path


STYLE = (Path(__file__).resolve().parents[1] / "frontend/src/player/styles/rewind.css").read_text(encoding="utf-8")
CHAPTERS = ("opening", "points", "specialty", "best-week", "badges", "placement", "finale")


def _luminance(hex_color):
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_each_rewind_chapter_has_a_distinct_readable_palette():
    expressions = re.findall(r"\.rewind-tone-([a-z-]+)\s*\{([^}]+)\}", STYLE)
    assert {name for name, _ in expressions} == set(CHAPTERS)
    palette_pairs = set()
    for name, body in expressions:
        tokens = dict(re.findall(r"--(scene-[a-z-]+):\s*(#[a-fA-F0-9]{6})\s*;", body))
        assert set(tokens) == {"scene-start", "scene-end", "scene-accent"}, name
        palette_pairs.add((tokens["scene-start"], tokens["scene-end"]))
        assert _contrast(tokens["scene-start"][1:], tokens["scene-accent"][1:]) >= 4.5, name
        assert _contrast(tokens["scene-end"][1:], tokens["scene-accent"][1:]) >= 4.5, name
    assert len(palette_pairs) == len(CHAPTERS)


def test_rewind_styles_keep_one_theme_system_and_reduced_motion_support():
    assert "var(--scene-accent)" in STYLE
    assert "var(--scene-start)" in STYLE
    assert "var(--scene-glow)" in STYLE
    assert "@media (prefers-reduced-motion: reduce)" in STYLE

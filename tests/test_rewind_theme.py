"""CREW Rewind must honor the shared brand palette without sacrificing contrast."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = (ROOT / "frontend/src/player/styles/rewind.css").read_text(encoding="utf-8")
SCRIPTS = (ROOT / "frontend/src/player/SeasonRewind.jsx").read_text(encoding="utf-8")
TOKENS = (ROOT / "app/static/css/crew-tokens.css").read_text(encoding="utf-8")
CHAPTERS = ("opening", "points", "specialty", "best-week", "badges", "placement", "finale")
GAME_COLORS = {
    "mystery": "#55e6ac",
    "trivia": "#ffbd45",
    "word": "#55b9ff",
    "tick-tock": "#c55cff",
}
ACCENTS = {
    "opening": "word",
    "points": "word",
    "specialty": "mystery",  # Default; overridden by the player's strongest game
    "best-week": "mystery",
    "badges": "tick-tock",
    "placement": "word",
    "finale": "trivia",  # Championship gold is reserved for the finale.
}


def _luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= .04045
        else ((channel + .055) / 1.055) ** 2.4
        for channel in channels
    ]
    return sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))


def _contrast(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + .05) / (low + .05)


def _brand_color(expression):
    match = re.fullmatch(r"var\(--(crew-game-[a-z-]+),\s*(#[a-fA-F0-9]{6})\)", expression)
    assert match is not None, expression
    name, fallback = match.groups()
    key = name.removeprefix("crew-game-")
    assert key in GAME_COLORS, key
    expected = GAME_COLORS[key]
    assert fallback.lower() == expected
    assert re.search(rf"--{re.escape(name)}:\s*{re.escape(expected)}\s*;", TOKENS)
    return expected


def test_rewind_chapters_use_official_game_colors_on_readable_dark_surfaces():
    expressions = re.findall(r"\.rewind-tone-([a-z-]+)\s*\{([^}]+)\}", STYLE)
    assert {name for name, _ in expressions} == set(CHAPTERS)
    pairs = set()
    for name, body in expressions:
        bg = dict(re.findall(r"--(scene-(?:start|end)):\s*(#[0-9a-fA-F]{6})\s*;", body))
        accent = re.search(r"--scene-accent:\s*(var\(--crew-game-[a-z-]+,\s*#[0-9a-fA-F]{6}\))\s*;", body)
        assert len(bg) == 2 and accent is not None, name
        expected_token = f"--crew-game-{ACCENTS[name]}"
        assert expected_token in accent.group(1)
        color = _brand_color(accent.group(1))
        pairs.add((bg["scene-start"], bg["scene-end"]))
        assert _contrast(bg["scene-start"][1:], color[1:]) >= 4.5, name
        assert _contrast(bg["scene-end"][1:], color[1:]) >= 4.5, name
    assert len(pairs) == len(CHAPTERS)


def test_signature_game_colors_are_shared_between_scene_and_chart():
    assert "GAME_COLORS[specialty?.key]" in SCRIPTS
    assert "' rewind-game-' + specialty.key" in SCRIPTS
    for game in GAME_COLORS:
        css_game = game.replace("-", "_")
        match = re.search(
            rf"\.rewind-tone-specialty\.rewind-game-{css_game}\s*\{{([^}}]+)\}}",
            STYLE,
        )
        assert match is not None
        assert _brand_color(re.search(
            r"--scene-accent:\s*(var\(--crew-game-[a-z-]+,\s*#[0-9a-fA-F]{6}\))\s*;",
            match.group(1),
        ).group(1)) == GAME_COLORS[game]
        assert f"var(--crew-game-{game}, {GAME_COLORS[game]})" in SCRIPTS


def test_rewind_keeps_crew_foundation_and_accessible_motion():
    assert "var(--crew-color-bg, #02070b)" in STYLE
    assert "var(--crew-font-body" in STYLE
    assert "var(--scene-accent)" in STYLE
    assert "var(--scene-glow)" in STYLE
    assert "--rewind-gold: var(--crew-game-trivia, #ffbd45)" in STYLE
    assert "@media (prefers-reduced-motion: reduce)" in STYLE

"""Static contract checks for the isolated HyperFrames teaser.

These do not claim an MP4 render succeeds: the real CLI must validate it separately.
"""
from html.parser import HTMLParser
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "prototypes" / "crew-hyperframes-teaser" / "index.html"


class CompositionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_teaser_has_a_bounded_hyperframes_composition():
    text = SOURCE.read_text(encoding="utf-8")
    parser = CompositionParser()
    parser.feed(text)

    roots = [attrs for _, attrs in parser.elements if attrs.get("data-composition-id")]
    assert len(roots) == 1
    root = roots[0]
    assert root["data-composition-id"] == "crewChampionshipTeaser"
    assert root["data-start"] == "0"
    assert root["data-duration"] == "12"
    assert root["data-width"] == "1920"
    assert root["data-height"] == "1080"

    clips = [attrs for _, attrs in parser.elements if "clip" in attrs.get("class", "").split()]
    assert len(clips) == 5
    for clip in clips:
        assert {"data-start", "data-duration", "data-track-index"} <= clip.keys()
        start, duration = float(clip["data-start"]), float(clip["data-duration"])
        assert 0 <= start < 12
        assert duration > 0
        assert start + duration <= 12.001

    assert "gsap.timeline({ paused: true" in text
    assert "window.__timelines.crewChampionshipTeaser = timeline" in text
    assert "setInterval(" not in text
    assert "setTimeout(" not in text


def test_teaser_stays_separate_from_gameplay_and_real_awards():
    text = SOURCE.read_text(encoding="utf-8")
    assert "THE TROPHY ROOM OPENS" in text
    assert "OCTOBER 19, 2026" in text
    assert "CREATIVE PREVIEW" in text
    assert "fetch(" not in text
    assert "localStorage" not in text
    assert "player_id" not in text
    assert "data-score" not in text
    assert "/api/" not in text

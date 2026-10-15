"""Player-facing achievements use 'badges' consistently sitewide.

Legacy /trophies routes, file paths and CSS class names remain unchanged to
avoid breaking links, storage, APIs and existing clients.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text()
TOUR = (ROOT / "frontend/src/player/TrophyWelcomeTour.jsx").read_text()
AUTH = (ROOT / "app/auth/routes.py").read_text()
CINEMA = (ROOT / "frontend/src/player/BadgeUnlockPreview.jsx").read_text()


def test_sitewide_navigation_and_unlock_copy_says_badges():
    assert "My badges" in MAIN
    assert "link('trophies','Badges'" in MAIN
    assert "'A new badge for your CREW collection.'" in CINEMA
    assert "BADGES UNLOCKED" in CINEMA
    assert "NEW AWARDS SAVED TO YOUR COLLECTION" in CINEMA
    assert "Continue to results" in CINEMA
    assert "My trophies" not in MAIN
    assert "link('trophies','Trophies'" not in MAIN
    assert "new trophy" not in MAIN.lower()
    assert "Trophy Room <span" not in MAIN
    assert '"label": "Badge"' in AUTH
    assert '"label": "Trophy"' not in AUTH


def test_all_tour_screens_have_concise_badge_only_copy():
    assert "PREVIEW ·" not in TOUR
    assert "CREW BADGES ·" not in TOUR
    assert "Built one detail at a time." not in TOUR
    assert "Four details. One badge." not in TOUR
    assert "BADGES UNLOCKED" in TOUR
    assert "Your badges are here" in TOUR
    assert "How a badge works" in TOUR
    assert "Your badge collection" in TOUR
    assert "Wear your badge" in TOUR
    assert "Explore badges" in TOUR
    assert "See my badges" in TOUR
    assert "Replay badge" in TOUR
    # Visible tour text should be scannable on mobile.
    start = TOUR.index("const ANATOMY_PHASES = [")
    end = TOUR.index("];", start)
    narration = TOUR[start:end]
    captions = re.findall(r"\['[A-Z ]+', '([^']+)'\]", narration)
    assert len(captions) == 4
    assert all(len(text.split()) <= 10 for text in captions)
    assert "trophy" not in TOUR.lower().split("const anatomy_phases = [",1)[1].split("export default",1)[0]
    assert "COMPLETE BADGE" in TOUR
    assert "COMPLETE MEDAL" not in TOUR
    # Component names and endpoint paths are not player-facing labels.
    assert "trophy_tour" not in TOUR
    assert "trophies" not in TOUR.lower().split("const headings =",1)[1].split("useeffect",1)[0]

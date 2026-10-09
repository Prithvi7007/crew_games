from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_home_shell_redesign_is_present():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend/src/player/styles/home.css").read_text(encoding="utf-8")

    assert "function AppHeader" in source
    assert "function HomePage" in source
    assert "'Home'" in source
    assert "crew-points-chip" in source
    assert "home-week" in source
    assert ".home-summary" in css

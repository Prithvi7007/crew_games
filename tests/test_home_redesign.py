from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_home_shell_redesign_is_present():
    header = (ROOT / "app/templates/_app_header.html").read_text()
    home = (ROOT / "app/templates/_home_v17.html").read_text()
    css = (ROOT / "app/static/css/home.css").read_text()
    assert ">Home<" in header
    assert ">Today<" not in header
    assert "crew-points-chip" in header
    assert "Your week." not in home
    assert "home-week" in home
    assert ".home-summary" in css

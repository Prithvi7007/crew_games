"""The home header promotes the season/week while retaining the dynamic date."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "frontend/src/player/main.jsx"
HOME_CSS = ROOT / "frontend/src/player/styles/home.css"


def test_home_season_week_is_primary_heading_and_date_is_eyebrow():
    source = MAIN.read_text(encoding="utf-8")
    home = source.split("function HomePage({ data })", 1)[1].split("function HomeDesktop(", 1)[0]
    heading = home.split('<div className="home-week">', 1)[1].split('<p>Four games. A week of fun.</p>', 1)[0]
    assert '<span className="v17-eyebrow">{weekLabel}</span>' in heading
    assert '<h1>{season ? `SEASON ${season.number} · WEEK ${String(season.week_number).padStart(2,\'0\')}`' in heading
    assert "weekNumber>0 ? `WEEK ${String(weekNumber).padStart(2,'0')}` : 'PRESEASON'" in heading
    assert heading.index('v17-eyebrow') < heading.index('<h1>')
    assert 'const weekLabel =' in home
    assert 'fp.month===lp.month' in home


def test_home_heading_maintains_consistent_type_scale_and_copy():
    source = MAIN.read_text(encoding="utf-8")
    css = HOME_CSS.read_text(encoding="utf-8")
    assert 'Four games. A week of fun.' in source
    assert '.home-week h1' in css
    assert '.v17-eyebrow' in css

"""Director-only stylesheet must be served without burdening guest assets."""
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def test_director_stylesheet_is_served_from_flask_static(client):
    response=client.get("/static/css/rewind-director.css")
    assert response.status_code==200
    assert response.mimetype=="text/css"
    assert b".rd-film" in response.data
    assert b".rd-trajectory" in response.data
    assert b"prefers-reduced-motion:reduce" in response.data


def test_guest_react_bundle_does_not_import_director_css():
    entry=(ROOT/"frontend/src/player/main.jsx").read_text()
    film=(ROOT/"frontend/src/player/RewindStoryFilmDirector.jsx").read_text()
    assert "import './styles/rewind-director" not in entry
    assert '<link rel="stylesheet" href="/static/css/rewind-director.css" />' in film
    assert "if(reduce){next();return;}" in film
    assert "NEXT CHAPTER" in film

"""Cinema preview is a genuine player-first film, not the Director slide shell."""
from datetime import date
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash
from app.db import create_profile, get_profile_by_id, profile_user_key, update_profile_role

ROOT=Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT/path).read_text(encoding="utf-8")


def test_cinema_uses_no_permanent_header_footer_or_chapter_progress_bars():
    film=source("frontend/src/player/RewindPlayerCinema.jsx")
    css=source("app/static/css/rewind-cinema.css")
    assert "rc-film" in film and "rc-moment" in film
    assert "rc-moment-hero" in film and "rc-moment-trajectory" in film
    assert "rd-metric-banner" not in film and "rd-ghost-number" not in film
    assert "rc-start-wrap" in film and "BEGIN YOUR REWIND" in film
    assert "rd-masthead" not in film and "rd-chapters" not in film
    assert "rd-footbar" not in film and "rd-foot-context" not in film
    assert "rc-chrome" in film and "rc-minimal-tools" in film
    assert "rc-progress" in film and "role=\"progressbar\"" in film
    assert ".rc-film {" in css and "height:100dvh" in css
    assert ".rc-moment-trajectory" in css
    assert ".rc-moment-insight.rc-kind-standout" in css
    assert "@media(max-width:700px)" in css
    assert "prefers-reduced-motion:reduce" in css


def test_cinema_has_safe_controls_and_does_not_fabricate_player_data():
    film=source("frontend/src/player/RewindPlayerCinema.jsx")
    assert "recap.cinematicStory" in film
    assert "RewindDirectorScenes beat={beat} recap={recap}" in film
    assert "useReducedMotion()" in film
    assert "window.clearTimeout" in film
    assert "window.removeEventListener" in film
    assert "aria-live=\"polite\"" in film
    assert "role=\"dialog\"" in film
    assert "setEvidence(true)" in film
    assert "mode=\"wait\"" in film
    assert "SamIam" not in film and "Juliet" not in film


def test_cinema_static_styles_are_served_without_adding_to_global_css(client):
    response=client.get("/static/css/rewind-cinema.css")
    assert response.status_code==200
    assert response.mimetype=="text/css"
    assert b".rc-moment-trajectory" in response.data
    entry=source("frontend/src/player/main.jsx")
    assert "data.rewindPlayerCinemaPreview === true" in entry
    assert "import './styles/rewind-cinema.css'" not in entry


def test_staff_only_cinema_does_not_replace_existing_rewind(app,client):
    with app.app_context():
        player=create_profile("FilmCinemaPlayer",generate_password_hash("test-password"),
                              "⭐",generate_password_hash("test-key"))
        admin=create_profile("FilmCinemaAdmin",generate_password_hash("test-admin-password"),
                             "⭐",generate_password_hash("test-admin-key"))
        pid,aid=int(player["id"]),int(admin["id"])
        update_profile_role(aid,"admin")

        def login(user_id):
            profile=get_profile_by_id(user_id)
            client.get("/login")
            with client.session_transaction() as session:
                session["user"]={
                    "profile_id":user_id,"username":profile["username"],
                    "role":profile["role"],"avatar":profile["avatar"],
                    "user_key":profile_user_key(user_id),
                    "session_version":int(profile["session_version"]),
                }
        login(aid)
        with patch("app.main.routes.crew_today",return_value=date(2026,10,26)):
            film=client.get("/rewind?preview=1&prototype=1&story=4&player=FilmCinemaPlayer")
            assert film.status_code==200
            assert b'"rewindPlayerCinemaPreview": true' in film.data
            assert b'"cinematicStory":' in film.data
            assert film.headers["Cache-Control"]=="private, no-store"
            for bad in ["/rewind?story=4",
                        "/rewind?preview=1&story=4",
                        "/rewind?prototype=1&story=4",
                        "/rewind?preview=1&prototype=1&story=4&analysis=1"]:
                assert client.get(bad).status_code==404
            director=client.get("/rewind?preview=1&prototype=1&story=3")
            assert director.status_code==200
            assert b'"rewindPlayerCinemaPreview": false' in director.data
        login(pid)
        with patch("app.main.routes.crew_today",return_value=date(2026,10,26)):
            assert client.get("/rewind?preview=1&prototype=1&story=4").status_code==404

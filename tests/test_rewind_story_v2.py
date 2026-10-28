"""Rewind V2 tests: one evidence engine, different stories, no fabricated results."""
from datetime import date
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app.db import (create_profile, finalize_game_stats, get_profile_by_id,
                    get_season_for_date, profile_user_key, update_profile_role)
from app.rewind_analytics import build_rewind_analytics
from app.rewind_story import build_rewind_story
from app.season_rewind import build_season_rewind

ROOT=Path(__file__).resolve().parents[1]
START=date(2026,9,21)


def item(pid,game,day,points):
    return {"profile_id":pid,"game_key":game,"game_date":day,"score":points}


def season():
    facts=[
        ("trivia","2026-09-22",[100,110,80,80,75]),
        ("word","2026-09-23",[50,100,70,50,60]),
        ("tick_tock","2026-09-24",[200,120,90,80,80]),
        ("mystery","2026-09-28",[100,105,60,60,30]),
    ]
    return [item(pid,g,day,points[pid-1]) for g,day,points in facts
            for pid in range(1,6)]


def story(rows,pid,names,rank,finalized=False):
    mine=[r for r in rows if r["profile_id"]==pid]
    insights=build_rewind_analytics(
        mine,rows,profile_id=pid,season_start=START,
        weeks_total=6,profile_names=names,rank=rank)
    recap={"analyticsStory":insights,"username":names[pid],
           "finalized":finalized,"rank":rank,
           "points":sum(r["score"] for r in mine)}
    return build_rewind_story(
        recap,rows,profile_id=pid,season_start=START,
        weeks_total=6,profile_names=names)


def test_narrow_finish_is_exactly_eighty_minus_sixty_five():
    names={1:"Sam",2:"Juliet",3:"Pat",4:"Rey",5:"Lee"}
    s=story(season(),1,names,1)
    assert s["title"]=="The 15-Point Finish"
    assert s["motif"]=="rivalry" and s["preview"] is True
    rivalry=next(b for b in s["beats"] if b["kind"]=="rivalry")["visual"]["rival"]
    assert rivalry["myTotal"]==450 and rivalry["theirTotal"]==435
    assert rivalry["weekly"][:2]==[
        {"week":1,"mine":350,"rival":330,"difference":20},
        {"week":2,"mine":450,"rival":435,"difference":15},
    ]
    pivot=next(b for b in s["beats"] if b["kind"]=="pivot")
    assert "Hypothetical" in pivot["description"] or "Without" in pivot["description"]
    swing=next(b for b in s["beats"] if b["kind"]=="swing")
    assert swing["visual"]=={"game":"Tick-Tock","edge":80,"other":-65,"net":15}
    assert "not a same-attempt skill comparison" in swing["evidence"]
    assert "current preview rank" in s["beats"][0]["evidence"]


def test_same_engine_produces_distinct_sam_and_juliet_stories():
    rows=season()
    names={1:"Sam",2:"Juliet",3:"Pat",4:"Rey",5:"Lee"}
    sam=story(rows,1,names,1)
    juliet=story(rows,2,names,2,finalized=True)
    assert sam["beats"]!=juliet["beats"]
    assert any(b["kind"]=="swing" for b in sam["beats"])
    assert not any(b["kind"]=="swing" for b in juliet["beats"])
    assert "behind Sam" in next(b for b in juliet["beats"]
                                if b["kind"]=="rivalry")["description"]
    assert "official final rank" in juliet["beats"][0]["evidence"]


def test_sparse_histories_get_no_fake_rival_or_strength():
    names={1:"Quiet",2:"Pat"}
    empty=story([],1,names,None)
    assert empty["motif"]=="unplayed"
    assert [b["kind"] for b in empty["beats"]]==["opening","ending"]
    assert "nothing to compare" in empty["beats"][0]["description"]
    one=story([item(1,"word","2026-09-23",70)],1,names,1)
    assert one["motif"]=="participation"
    assert [b["kind"] for b in one["beats"]]==["opening","ending"]
    assert "champion" not in str(one).lower()


def test_v2_is_staff_only_and_previous_rewind_is_preserved(app,client):
    with app.app_context():
        current=get_season_for_date(date(2026,10,26))
        p=create_profile("V2SamplePlayer",generate_password_hash("test-password"),
                         "⭐",generate_password_hash("test-key"))
        admin=create_profile("V2Admin",generate_password_hash("admin-password"),
                             "⭐",generate_password_hash("admin-key"))
        pid,aid=int(p["id"]),int(admin["id"])
        update_profile_role(aid,"admin")
        finalize_game_stats(profile_user_key(pid),"trivia","2026-09-22",88,True)
        data=build_season_rewind(pid,current,admin_preview=True)
        assert data["cinematicStory"]["player"]=="V2SamplePlayer"
        assert data["cinematicStory"]["preview"] is True

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
            response=client.get(
                "/rewind?preview=1&prototype=1&story=2&player=V2SamplePlayer")
            assert response.status_code==200
            assert b'"rewindStoryPreview": true' in response.data
            assert b'"cinematicStory":' in response.data
            assert response.headers["Cache-Control"]=="private, no-store"
            assert client.get("/rewind?preview=1&story=2").status_code==404
            assert client.get("/rewind?prototype=1&story=2").status_code==404
            assert client.get("/rewind?preview=1&prototype=1&analysis=1&story=2").status_code==404
            legacy=client.get("/rewind?preview=1&prototype=1")
            assert legacy.status_code==200
            assert b'"rewindStoryPreview": false' in legacy.data
        login(pid)
        with patch("app.main.routes.crew_today",return_value=date(2026,10,26)):
            assert client.get("/rewind?preview=1&prototype=1&story=2").status_code==404


def test_new_film_consumes_evidence_without_hardcoded_players():
    main=(ROOT/"frontend/src/player/main.jsx").read_text()
    film=(ROOT/"frontend/src/player/RewindStoryFilm.jsx").read_text()
    css=(ROOT/"frontend/src/player/styles/rewind-story-film.css").read_text()
    assert "data.rewindStoryPreview === true" in main
    assert "recap.cinematicStory" in film
    assert "beats.map(" in film
    assert "useReducedMotion()" in film
    assert "rewind-v2-progress" in film
    assert "100dvh" in css and "overflow-y:auto" in css
    assert "SamIam" not in film and "Juliet" not in film

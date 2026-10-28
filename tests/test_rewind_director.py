"""Director film: real scenes, rival trajectory, evidence safeguards, private access."""
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.rewind_analytics import build_rewind_analytics
from app.rewind_story import build_rewind_story
from app.db import create_profile, get_profile_by_id, get_season_for_date, profile_user_key, update_profile_role
from werkzeug.security import generate_password_hash

ROOT=Path(__file__).resolve().parents[1]
START=date(2026,9,21)
NAMES={1:"Alex",2:"Jordan",3:"Avery",4:"Remy",5:"Quinn"}
WEEKS=["2026-09-22","2026-09-29","2026-10-06","2026-10-13","2026-10-20","2026-10-27"]


def row(pid,game,day,score):
    return {"profile_id":pid,"game_key":game,"game_date":day,"score":score}


def build(rows,pid,rank,finalized=False):
    mine=[r for r in rows if r["profile_id"]==pid]
    recap={"username":NAMES[pid],"rank":rank,"finalized":finalized,
           "points":sum(r["score"] for r in mine),
           "analyticsStory":build_rewind_analytics(
               mine,rows,profile_id=pid,season_start=START,
               weeks_total=6,profile_names=NAMES,rank=rank)}
    return build_rewind_story(recap,rows,profile_id=pid,season_start=START,
                              weeks_total=6,profile_names=NAMES)


def six_week_rows():
    # Six scheduled weeks, same trivia question cohorts.
    samples={
        1:[60,50,70,90,50,80],
        2:[65,75,45,70,70,60],
        3:[35,40,45,50,35,30],
        4:[30,40,25,35,40,30],
        5:[20,30,25,30,20,15],
    }
    return [row(pid,"trivia",day,score)
            for pid,scores in samples.items()
            for day,score in zip(WEEKS,scores)]


def test_trajectory_is_scheduled_week_points_not_an_invented_live_race():
    rows=six_week_rows()
    alex=build(rows,1,1)
    jordan=build(rows,2,2)
    assert alex["title"]=="The 15-Point Finish"
    assert alex["motif"]=="rivalry"
    scenes={beat["kind"]:beat for beat in alex["beats"]}
    assert "trajectory" in scenes
    history=scenes["trajectory"]["visual"]["rival"]["weekly"]
    assert len(history)==6
    assert history[0]=={"week":1,"mine":60,"rival":65,"difference":-5}
    assert history[-1]=={"week":6,"mine":400,"rival":385,"difference":15}
    turning=scenes["trajectory"]["visual"]["rival"]["turning"]
    assert turning=={"week":2,"delta":-25}
    assert "scheduled puzzle week" in scenes["trajectory"]["evidence"]
    assert "trajectory" in {beat["kind"] for beat in jordan["beats"]}
    assert jordan["beats"]!=alex["beats"]
    assert "behind" in next(b for b in jordan["beats"] if b["kind"]=="rivalry")["description"]


def test_same_puzzle_comparison_is_taken_from_winning_day_not_last_attempt():
    data=[
        row(1,"trivia","2026-09-22",100),
        row(1,"word","2026-09-23",15),
        row(2,"trivia","2026-09-22",80),
        row(3,"trivia","2026-09-22",70),
        row(4,"trivia","2026-09-22",60),
        row(2,"word","2026-09-23",10),
        row(3,"word","2026-09-23",20),
        row(4,"word","2026-09-23",20),
    ]
    mine=data[:2]
    insights=build_rewind_analytics(mine,data,profile_id=1,
          season_start=START,weeks_total=6,profile_names=NAMES,rank=1)
    card=next(c for c in insights["cards"] if c["key"]=="same_puzzle")
    assert card["comparison"]=={
        "game":"Trivia","score":100,"peerMedian":70,
        "outscored":3,"peerCount":3
    }
    story=build_rewind_story(
        {"analyticsStory":insights,"username":"Alex","rank":1,"finalized":False,
         "points":115},data,profile_id=1,season_start=START,
         weeks_total=6,profile_names=NAMES)
    standout=next(b for b in story["beats"] if b["kind"]=="standout")
    assert standout["visual"]["peerMedian"]==70


def test_negative_peer_gap_is_not_mislabeled_hidden_strength():
    rows=[row(1,"trivia",WEEKS[0],35),row(1,"trivia",WEEKS[1],40)]
    rows.extend(row(pid,"trivia",WEEKS[0],80) for pid in [2,3,4])
    report=build_rewind_analytics(rows[:2],rows,profile_id=1,
        season_start=START,weeks_total=6,profile_names=NAMES,rank=4)
    assert not any(card["key"]=="relative_strength" for card in report["cards"])


def test_story_render_source_has_data_provenance_and_controls():
    entry=(ROOT/"frontend/src/player/main.jsx").read_text()
    controller=(ROOT/"frontend/src/player/RewindStoryFilmDirector.jsx").read_text()
    scenes=(ROOT/"frontend/src/player/RewindDirectorScenes.jsx").read_text()
    styles=(ROOT/"app/static/css/rewind-director.css").read_text()
    assert '/static/css/rewind-director.css' in controller
    assert "data.rewindStoryDirectorPreview === true" in entry
    assert "recap.cinematicStory" in controller
    assert "See how we know" in controller
    assert "useReducedMotion()" in controller
    assert "performance.now()" in controller
    assert "setTimeout" in controller
    assert "turningWeek" in scenes
    assert "rival.weekly" in scenes
    assert "visual.peers" in scenes
    assert "visual.peerMedian" in scenes
    assert "SamIam" not in scenes and "Juliet" not in controller
    assert "prefers-reduced-motion:reduce" in styles


def test_director_preview_keeps_previous_staff_films_and_guards_player_access(app,client):
    with app.app_context():
        user=create_profile("DirectorPlayer",generate_password_hash("sufficient-test-password"),
                            "⭐",generate_password_hash("test-key-player"))
        admin=create_profile("DirectorAdmin",generate_password_hash("sufficient-test-password"),
                             "⭐",generate_password_hash("test-key-admin"))
        pid,aid=int(user["id"]),int(admin["id"])
        update_profile_role(aid,"admin")
        def login(uid):
            profile=get_profile_by_id(uid)
            client.get("/login")
            with client.session_transaction() as session:
                session["user"]={
                    "profile_id":uid,"username":profile["username"],
                    "role":profile["role"],"avatar":profile["avatar"],
                    "user_key":profile_user_key(uid),
                    "session_version":int(profile["session_version"]),
                }
        login(aid)
        with patch("app.main.routes.crew_today",return_value=date(2026,10,26)):
            view=client.get("/rewind?preview=1&prototype=1&story=3&player=DirectorPlayer")
            assert view.status_code==200
            assert b'"rewindStoryDirectorPreview": true' in view.data
            assert b'"cinematicStory":' in view.data
            assert view.headers["Cache-Control"]=="private, no-store"
            assert client.get("/rewind?story=3").status_code==404
            assert client.get("/rewind?preview=1&story=3").status_code==404
            assert client.get("/rewind?prototype=1&story=3").status_code==404
            assert client.get("/rewind?preview=1&prototype=1&analysis=1&story=3").status_code==404
            v2=client.get("/rewind?preview=1&prototype=1&story=2")
            assert v2.status_code==200
            assert b'"rewindStoryDirectorPreview": false' in v2.data
        login(pid)
        with patch("app.main.routes.crew_today",return_value=date(2026,10,26)):
            assert client.get("/rewind?preview=1&prototype=1&story=3").status_code==404

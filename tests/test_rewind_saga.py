"""Season Saga — evidence, title eligibility, responsive private preview."""
from datetime import date
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app.db import create_profile, finalize_game_stats, profile_user_key, get_season_for_date, update_profile_role
from app.rewind_saga import build_season_saga
from app.season_rewind import build_season_rewind

def player(name,role=None):
    p=create_profile(name,generate_password_hash("test-password"),"⭐",
                     generate_password_hash("test-key")); pid=int(p["id"])
    if role:update_profile_role(pid,role)
    return pid

def test_saga_calculates_eligible_weeks_game_averages_and_dna(app):
    with app.app_context():
        season=get_season_for_date(date(2026,10,26))
        me=player("SagaMe");a=player("SagaA");b=player("SagaB");c=player("SagaC")
        for pid,items in [
          (me,[("2026-09-22","trivia",80),("2026-09-23","word",60),
               ("2026-09-29","trivia",90),("2026-09-30","word",70)]),
          (a,[("2026-09-22","trivia",100),("2026-09-29","word",80)]),
          (b,[("2026-09-22","word",90),("2026-09-29","trivia",95)]),
          (c,[("2026-09-22","trivia",70)])]:
            for day,key,score in items:finalize_game_stats(profile_user_key(pid),key,day,score,True)
        saga=build_season_rewind(me,season,admin_preview=True)["seasonSaga"]
        kinds=[item["kind"] for item in saga["beats"]]
        assert kinds[0]=="welcome"
        assert "winner" not in kinds and "winner_badge" not in kinds
        assert "podium" in kinds
        assert "weekly_trend" in kinds and "peak_week" in kinds
        assert "game_compare" in kinds and "game_dna" in kinds
        assert kinds[-2:]==["legacy","season_two"]
        trend=next(b for b in saga["beats"] if b["kind"]=="weekly_trend")["visual"]
        assert trend["weeks"][0]["mine"]==140
        assert trend["weeks"][0]["highest"]==140
        assert trend["bestWeek"]==2
        comp=next(b for b in saga["beats"] if b["kind"]=="game_compare")["visual"]["games"]
        trivia=next(g for g in comp if g["key"]=="trivia")
        assert trivia["mine"]==85
        assert trivia["crew"]==88.3
        dna=next(b for b in saga["beats"] if b["kind"]=="game_dna")["visual"]
        assert sum(g["played"] for g in dna["games"])==4
        assert sum(g["points"] for g in dna["games"])==300
        assert sum(g["gameShare"] for g in dna["games"])==100

def test_championship_claim_requires_approved_winner_and_badge():
    recap={"username":"x","finalized":True,"rank":1,"signature":None,
           "analyticsStory":{"cards":[]}}
    winners={"season_champion":[{"profile_id":1,"points":100}],
             "season_trivia_master":[{"profile_id":1,"points":70}],
             "season_wordle_master":[{"profile_id":2,"points":60}]}
    saga=build_season_saga(
        recap,[],profile_id=1,season_start=date(2026,9,21),
        weeks_total=6,names={1:"x"},official_winners=winners,
        awarded_codes={"season_champion","season_trivia_master","brainiac"})
    beats=saga["beats"]
    assert [b["kind"] for b in beats[:4]]==["winner","winner_badge","winner","winner_badge"]
    assert [b["visual"]["badge"]["code"] for b in beats if b["kind"]=="winner_badge"]==[
        "season_champion","season_trivia_master"]
    vault=next(b for b in beats if b["kind"]=="trophy_vault")
    assert set(vault["visual"]["celebrated"])=={"season_champion","season_trivia_master"}
    assert len(vault["visual"]["badges"])==3
    assert [b["kind"] for b in beats[-2:]]==["legacy","season_two"]

def test_saga_theme_is_original_crew_and_preview_requires_staff(app,client):
    root=Path(__file__).resolve().parents[1]
    css=(root/"app/static/css/rewind-saga.css").read_text()
    jsx=(root/"frontend/src/player/RewindSagaScene.jsx").read_text()
    assert "--crew-game-trivia" in css and "--crew-game-word" in css
    assert "--crew-game-mystery" in jsx and "--crew-game-tick-tock" in jsx
    assert "BadgeMedallion" in jsx and "SamIam" not in jsx
    with app.app_context():
        p=player("SagaOwner","admin")
        from app.db import get_profile_by_id
        profile=get_profile_by_id(p)
        user={"profile_id":p,"username":profile["username"],"role":profile["role"],
              "avatar":profile["avatar"],"user_key":profile_user_key(p),
              "session_version":int(profile["session_version"])}
    client.get("/login")
    with client.session_transaction() as sess:sess["user"]=user
    with patch("app.main.routes.crew_today",return_value=date(2026,10,26)):
        response=client.get("/rewind?preview=1&prototype=1&story=5")
        assert response.status_code==200
        assert b'"rewindSeasonSagaPreview": true' in response.data
        assert response.headers["Cache-Control"]=="private, no-store"
        assert client.get("/rewind?story=5").status_code==404
        assert client.get("/rewind?preview=1&story=5").status_code==404
        assert client.get("/rewind?prototype=1&story=5").status_code==404

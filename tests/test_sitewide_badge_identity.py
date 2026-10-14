"""Sitewide verified badge identity, private try-on and motion contracts."""
import json
import re
from datetime import date

from werkzeug.security import generate_password_hash

from app.badge_store import award_badges, get_badge_awards, get_showcase, set_showcase_slot
from app.db import (
    create_profile, finalize_game_stats, get_profile_by_id, get_season_for_date,
    profile_user_key, update_profile_role,
)


def _data(response):
    assert response.status_code == 200
    match = re.search(r'<script[^>]*id="player-state"[^>]*>(.*?)</script>',
                      response.get_data(as_text=True), flags=re.DOTALL)
    assert match
    return json.loads(match.group(1))


def _user(app, name, role="player"):
    with app.app_context():
        profile = create_profile(
            name, generate_password_hash("badge-test-password"),
            "🏆", generate_password_hash("badge-test-recovery"),
        )
        profile_id = int(profile["id"])
        if role != "player":
            update_profile_role(profile_id, role)
        return profile_id


def _signin(client, app, profile_id):
    with app.app_context():
        profile = get_profile_by_id(profile_id)
    client.get("/login")
    with client.session_transaction() as sess:
        sess["user"] = {
            "profile_id": profile_id, "username": profile["username"],
            "avatar": profile["avatar"], "role": profile["role"],
            "user_key": profile_user_key(profile_id),
            "session_version": int(profile["session_version"]),
        }
        return sess["csrf_token"]


def _clock(monkeypatch, day):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: day)
    monkeypatch.setattr("app.trophy_tour.crew_today", lambda: day)
    monkeypatch.setattr("app.main.routes.crew_today", lambda: day)
    monkeypatch.setattr("app.schedule.crew_today", lambda: day)


def _give_and_equip(app, profile_id, badge_code):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 12))
        award_badges(profile_id, season["id"], [badge_code])
        award_id = next(int(a["id"]) for a in get_badge_awards(profile_id, season["id"])
                        if a["badge_code"] == badge_code)
        set_showcase_slot(profile_id, 1, award_id)
        return award_id


def test_public_equipped_badge_is_shared_between_header_profile_and_rankings_api(
    app, client, monkeypatch,
):
    _clock(monkeypatch, date(2026, 10, 19))
    alpha = _user(app, "IdentityAlpha")
    beta = _user(app, "IdentityBeta")
    _give_and_equip(app, alpha, "case_closed")
    _give_and_equip(app, beta, "sharp_shooter")
    with app.app_context():
        finalize_game_stats(profile_user_key(alpha), "mystery", "2026-10-12", 100,
                            True, competitive=True)
        finalize_game_stats(profile_user_key(beta), "mystery", "2026-10-12", 75,
                            True, competitive=True)
    _signin(client, app, alpha)
    page = _data(client.get("/home"))
    assert page["shell"]["userEquippedBadge"]["code"] == "case_closed"
    assert page["shell"]["userEquippedBadge"]["seasonNumber"] == 1
    assert page["shell"]["userEquippedBadge"].get("preview") is None
    assert _data(client.get("/games"))["shell"]["userEquippedBadge"]["code"] == "case_closed"
    assert _data(client.get("/profile"))["equippedBadge"] == page["shell"]["userEquippedBadge"]
    first = _data(client.get("/leaderboard"))
    ranked = {p["username"]: p["equippedBadge"] for p in first["board"]["players"]}
    assert ranked["IdentityAlpha"]["code"] == "case_closed"
    assert ranked["IdentityBeta"]["code"] == "sharp_shooter"
    filtered = client.get("/api/leaderboard?week=all&game=mystery")
    assert filtered.status_code == 200
    ranked_api = {p["username"]: p["equippedBadge"] for p in filtered.get_json()["players"]}
    assert ranked_api["IdentityAlpha"]["code"] == "case_closed"
    assert ranked_api["IdentityBeta"]["code"] == "sharp_shooter"


def test_admin_private_preview_visible_in_own_rankings_not_other_players(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 12))
    admin = _user(app, "IdentityAdmin", "admin")
    _give_and_equip(app, admin, "word_wizard")
    with app.app_context():
        finalize_game_stats(profile_user_key(admin), "mystery", "2026-10-12", 100,
                            True, competitive=True)
    token = _signin(client, app, admin)
    preview = client.post("/api/trophies/preview-badge", json={"badgeCode": "unicorn"},
                          headers={"X-CSRFToken": token})
    assert preview.status_code == 200
    badge = _data(client.get("/home"))["shell"]["userEquippedBadge"]
    assert badge["code"] == "unicorn"
    assert badge["preview"] is True
    assert _data(client.get("/profile"))["equippedBadge"]["code"] == "unicorn"
    rankings = _data(client.get("/leaderboard"))["board"]
    own = next(p for p in rankings["players"] if p["username"] == "IdentityAdmin")
    assert own["equippedBadge"]["code"] == "unicorn"
    assert own["equippedBadge"]["preview"] is True
    assert rankings["me"]["equippedBadge"]["code"] == "unicorn"
    assert rankings["top"][0]["equippedBadge"]["code"] == "unicorn"
    api = client.get("/api/leaderboard").get_json()
    api_me = next(p for p in api["players"] if p["username"] == "IdentityAdmin")
    assert api_me["equippedBadge"]["code"] == "unicorn"
    assert api_me["equippedBadge"]["preview"] is True
    # Another authenticated viewer sees only this admin's real equipped badge.
    viewer = _user(app, "IdentityViewer", "owner")
    other_client = app.test_client()
    _signin(other_client, app, viewer)
    other_board = _data(other_client.get("/leaderboard"))["board"]
    seen = next(p for p in other_board["players"] if p["username"] == "IdentityAdmin")
    assert seen["equippedBadge"]["code"] == "word_wizard"
    assert seen["equippedBadge"].get("preview") is None
    other_api = other_client.get("/api/leaderboard?game=mystery").get_json()
    seen_api = next(p for p in other_api["players"] if p["username"] == "IdentityAdmin")
    assert seen_api["equippedBadge"]["code"] == "word_wizard"
    assert seen_api["equippedBadge"].get("preview") is None
    with app.app_context():
        stored = get_showcase(admin)
        assert [p["badge_code"] for p in stored] == ["word_wizard"]
        assert stored[0]["season_number"] == 1
    # Removing a preview restores a verified real medal in the same session.
    clear = client.post("/api/trophies/preview-badge", json={"badgeCode": None},
                        headers={"X-CSRFToken": token})
    assert clear.status_code == 200
    assert _data(client.get("/home"))["shell"]["userEquippedBadge"]["code"] == "word_wizard"
    cleared = _data(client.get("/leaderboard"))["board"]["me"]["equippedBadge"]
    assert cleared["code"] == "word_wizard"
    assert cleared.get("preview") is None
    client.post("/logout", headers={"X-CSRFToken": token})
    _signin(client, app, admin)
    assert _data(client.get("/home"))["shell"]["userEquippedBadge"]["code"] == "word_wizard"


def test_early_launch_gate_keeps_player_header_and_ranking_badges_hidden(
    app, client, monkeypatch,
):
    _clock(monkeypatch, date(2026, 10, 12))
    player = _user(app, "IdentityBeforeLaunch")
    _give_and_equip(app, player, "case_closed")
    with app.app_context():
        finalize_game_stats(profile_user_key(player), "mystery", "2026-10-12", 100,
                            True, competitive=True)
    _signin(client, app, player)
    assert _data(client.get("/home"))["shell"]["userEquippedBadge"] is None
    assert _data(client.get("/profile"))["equippedBadge"] is None
    board = _data(client.get("/leaderboard"))["board"]
    assert all("equippedBadge" not in p for p in board["players"])
    api_board = client.get("/api/leaderboard").get_json()
    assert all("equippedBadge" not in p for p in api_board["players"])


def test_compact_avatar_and_two_motion_experiences_have_accessible_fallbacks():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    main = (root / "frontend/src/player/main.jsx").read_text()
    trophy = (root / "frontend/src/player/TrophyRoom.jsx").read_text()
    tour = (root / "frontend/src/player/TrophyWelcomeTour.jsx").read_text()
    trophy_style = (root / "frontend/src/player/styles/trophies.css").read_text()
    tour_style = (root / "frontend/src/player/styles/trophy-tour.css").read_text()
    ranks_style = (root / "frontend/src/player/styles/rankings.css").read_text()
    assert 'size="compact"' in main
    assert 'player.equippedBadge' in main
    assert 'shell.userEquippedBadge' in main
    assert "size === 'compact'" in trophy
    assert 'crew-badge-apply-toast' in trophy
    assert 'role="status" aria-live="polite"' in trophy
    assert "window.clearTimeout(timeout)" in trophy
    assert "crew-badge-applied" in trophy_style
    assert "prefers-reduced-motion:reduce" in trophy_style
    assert "rankings-player-medal" in ranks_style
    assert 'className="crew-tour-stage" key={step}' in tour
    assert "crew-tour-arrival" in tour_style
    assert "crew-tour-curtain" in tour_style
    assert "prefers-reduced-motion:reduce" in tour_style


def test_unranked_owner_preview_visible_after_rankings_filter_refresh(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 12))
    owner = _user(app, "IdentityUnrankedOwner", "owner")
    token = _signin(client, app, owner)
    response = client.post(
        "/api/trophies/preview-badge",
        json={"badgeCode": "season_champion"},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200
    first = _data(client.get("/leaderboard"))["board"]
    assert all(p["profile_id"] != owner for p in first["players"])
    assert first["me"]["profile_id"] == owner
    assert first["me"]["rank"] is None
    assert first["me"]["equippedBadge"]["code"] == "season_champion"
    assert first["me"]["equippedBadge"]["preview"] is True
    for query in (
        "/api/leaderboard?week=all&game=all",
        "/api/leaderboard?week=1&game=trivia",
    ):
        latest = client.get(query).get_json()
        assert all(p["profile_id"] != owner for p in latest["players"])
        assert latest["me"]["equippedBadge"]["code"] == "season_champion"
        assert latest["me"]["equippedBadge"]["preview"] is True
        assert latest["me"]["rank"] is None
    # Preview removal restores the plain avatar, creates no awards or showcase.
    cleared = client.post(
        "/api/trophies/preview-badge",
        json={"badgeCode": None},
        headers={"X-CSRFToken": token},
    )
    assert cleared.status_code == 200
    assert client.get("/api/leaderboard").get_json()["me"]["equippedBadge"] is None
    with app.app_context():
        assert get_showcase(owner) == []
        season = get_season_for_date(date(2026, 10, 12))
        assert get_badge_awards(owner, season["id"]) == []


def test_unranked_badge_row_is_view_only_not_fictional_rank():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    style = (root / "frontend/src/player/styles/rankings.css").read_text(encoding="utf-8")
    assert "const unrankedMe=board.me?.equippedBadge" in source
    assert "!rankedPlayers.some(player=>player.profile_id===board.me.profile_id)" in source
    assert "const visiblePlayers=unrankedMe ? [...rankedPlayers,unrankedMe]" in source
    assert "visiblePlayers.map(player=>" in source
    assert "hidden={visiblePlayers.length>0}" in source
    assert "Unranked in this filter" in source
    assert "PRIVATE PREVIEW" in source
    assert ".rankings-leader-row.is-unranked" in style


def test_prelaunch_player_cannot_leak_admin_preview_into_public_rankings(
    app, client, monkeypatch,
):
    _clock(monkeypatch, date(2026, 10, 18))
    admin = _user(app, "PreviewPrelaunchAdmin", "admin")
    player = _user(app, "PreviewPrelaunchPlayer", "player")
    _give_and_equip(app, admin, "case_closed")
    with app.app_context():
        finalize_game_stats(profile_user_key(admin), "mystery", "2026-10-12", 100,
                            True, competitive=True)
    token = _signin(client, app, admin)
    assert client.post(
        "/api/trophies/preview-badge",
        json={"badgeCode": "unicorn"},
        headers={"X-CSRFToken": token},
    ).status_code == 200
    # Early preview remains visible to that admin alone.
    own = _data(client.get("/leaderboard"))["board"]["me"]
    assert own["equippedBadge"]["code"] == "unicorn"
    # A normal player sees no badges anywhere in the Rankings API yet.
    other = app.test_client()
    _signin(other, app, player)
    result = other.get("/api/leaderboard").get_json()
    assert all("equippedBadge" not in item for item in result["players"])
    assert result["me"] is None or "equippedBadge" not in result["me"]

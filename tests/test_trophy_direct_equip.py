"""Trophy Room direct card equipment: accessibility and persistence contracts."""
from datetime import date
from pathlib import Path

from app.badge_store import award_badges, get_badge_awards, get_showcase
from app.db import create_profile, get_season_for_date, profile_user_key

ROOT = Path(__file__).resolve().parents[1]
JSX = ROOT / "frontend/src/player/TrophyRoom.jsx"
CSS = ROOT / "frontend/src/player/styles/trophies.css"


def test_unlocked_badges_are_direct_clickable_controls():
    source = JSX.read_text(encoding="utf-8")
    styles = CSS.read_text(encoding="utf-8")

    assert 'const canEquip = Boolean(badge.earned && badge.awardId);' in source
    assert "const Surface = canEquip ? 'button' : 'div';" in source
    assert "'aria-pressed': isEquipped" in source
    assert "disabled: saving" in source
    assert "onClick: () => onSelect(badge.awardId)" in source
    assert "onSelect={selectBadge}" in source
    assert "badge.earned && item.awardId === awardId" not in source  # no stale ownership check
    assert "item.earned && item.awardId === awardId" in source
    assert 'className="trophy-badge-surface"' in source
    assert ".trophy-badge-card button.trophy-badge-surface:focus-visible" in styles
    assert ".trophy-badge-card.is-equipped" in styles
    assert "trophy-equipped-mark" in source
    assert "✓ EQUIPPED" in source
    assert "◇ LOCKED" in source


def test_dropdown_panel_is_removed_and_save_flow_preserved():
    source = JSX.read_text(encoding="utf-8")
    styles = CSS.read_text(encoding="utf-8")

    assert 'className="trophy-single-equip"' not in source
    assert 'id="trophy-equip-select"' not in source
    assert "trophy-single-equip" not in styles
    assert "const removing = equipped?.awardId === awardId" in source
    assert "saveSlot(1, removing ? null : awardId)" in source
    assert "setShowcase(result.showcase || [])" in source
    assert 'role="status" aria-live="polite"' in source
    assert "if (saving) return" in source


def test_single_profile_slot_can_switch_and_unequip_via_api(app, client, monkeypatch):
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: date(2026, 10, 19))
    client.get("/login")
    with app.app_context():
        profile = create_profile("DirectEquip", "password-hash", "🏆", "recovery-hash")
        profile_id = int(profile["id"])
        user = {
            "profile_id": profile_id,
            "username": profile["username"],
            "avatar": profile["avatar"],
            "role": "player",
            "user_key": profile_user_key(profile_id),
            "session_version": int(profile["session_version"]),
        }
        season = get_season_for_date(date(2026, 10, 12))
        assert season is not None
        award_badges(profile_id, season["id"], ("case_closed", "mind_reader"), source_date="2026-10-12")
        awarded = {row["badge_code"]: int(row["id"]) for row in get_badge_awards(profile_id, season["id"])}

    with client.session_transaction() as session:
        session["user"] = user
        token = session["csrf_token"]
    headers = {"X-CSRFToken": token}

    def set_equipped(award_id):
        return client.post(
            "/api/trophies/showcase",
            json={"slot": 1, "awardId": award_id},
            headers=headers,
        )

    first = set_equipped(awarded["case_closed"])
    assert first.status_code == 200
    assert [entry["badgeCode"] for entry in first.json["showcase"]] == ["case_closed"]

    switched = set_equipped(awarded["mind_reader"])
    assert switched.status_code == 200
    assert [entry["badgeCode"] for entry in switched.json["showcase"]] == ["mind_reader"]

    cleared = set_equipped(None)
    assert cleared.status_code == 200
    assert cleared.json["showcase"] == []
    with app.app_context():
        assert get_showcase(profile_id) == []

    # The server must still reject badges not awarded to this player.
    assert set_equipped(999999).status_code == 400

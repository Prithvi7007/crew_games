"""Verified badge identity for the app shell and public leaderboard.

Only persisted, server-awarded showcase choices are visible to other players.
Private admin/owner try-ons are overlaid for the signed-in user only.
"""
from flask import session

from app.badges import BADGES_BY_CODE
from app.db import get_db
from app.trophy_access import trophy_preview_enabled, trophies_visible_to


def _badge_payload(code, season_number):
    definition = BADGES_BY_CODE.get(code)
    if not definition:
        return None
    return {
        "code": definition.code, "name": definition.name,
        "rarity": definition.rarity, "gameKey": definition.game_key,
        "vertical": definition.vertical, "seasonNumber": int(season_number),
    }


def _equipped_rows(profile_ids):
    """One parametrized lookup for requested profiles, without an N+1 loop."""
    ids = sorted({int(profile_id) for profile_id in profile_ids if profile_id is not None})
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = get_db().execute(
        f"""SELECT bs.profile_id, ba.badge_code, s.season_number
            FROM badge_showcase AS bs
            JOIN badge_awards AS ba
              ON ba.id = bs.badge_award_id AND ba.profile_id = bs.profile_id
            JOIN seasons AS s ON s.id = ba.season_id
            WHERE bs.slot = 1 AND bs.profile_id IN ({placeholders})""",
        ids,
    ).fetchall()
    return {
        int(row["profile_id"]): badge
        for row in rows
        if (badge := _badge_payload(row["badge_code"], row["season_number"]))
    }


def equipped_badge_for_viewer(user):
    """Current player's visible badge, with session-only admin preview."""
    if not trophies_visible_to(user):
        return None
    profile_id = int(user["profile_id"])
    real_badge = _equipped_rows([profile_id]).get(profile_id)
    if not trophy_preview_enabled(user):
        return real_badge
    code = session.get("trophy_preview_badge_code")
    if code not in BADGES_BY_CODE:
        return real_badge
    # Preview has no award; season number comes from the active/most recent season.
    from app.db import get_season_for_date, list_seasons
    from app.schedule import crew_today
    today = crew_today()
    season = get_season_for_date(today)
    if season is None:
        season = next((item for item in list_seasons(today)
                       if item["start_date"] <= today), None)
    number = season["number"] if season else 1
    return {**_badge_payload(code, number), "preview": True}


def with_public_equipped_badges(board, viewer):
    """Decorate the initial standings and AJAX refresh identically.

    An administrator's session-only preview is visible ONLY to themselves.
    Other viewers see verified, persisted awards and never private try-ons.
    """
    if not trophies_visible_to(viewer):
        return board
    players = board.get("players", [])
    me = board.get("me")
    top = board.get("top", [])
    ids = [player.get("profile_id") for player in players]
    if me:
        ids.append(me.get("profile_id"))
    badge_map = _equipped_rows(ids)
    viewer_id = int(viewer["profile_id"])
    preview_code = session.get("trophy_preview_badge_code")
    private_preview = (
        equipped_badge_for_viewer(viewer)
        if trophy_preview_enabled(viewer) and preview_code in BADGES_BY_CODE
        else None
    )

    def visible_badge(player):
        if player is None:
            return None
        # Player identity is always server-owned, never supplied by the client.
        # The preview is scoped to THIS response and never stored on the board.
        player_id = player.get("profile_id")
        if player_id == viewer_id and private_preview:
            return private_preview
        return badge_map.get(player_id)

    for player in players:
        player["equippedBadge"] = visible_badge(player)
    if me is not None:
        me["equippedBadge"] = visible_badge(me)
    for player in top:
        player["equippedBadge"] = visible_badge(player)
    return board

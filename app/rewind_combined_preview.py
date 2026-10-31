"""Read-only composition of staff championship previews and real season stories."""
from app.championships import preview_season_championships
from app.db import get_db
from app.rewind_champion_preview import CHOICES, build_champion_preview


def rewind_preview_players():
    """Expose only display names, and only when the route authorizes staff."""
    rows = get_db().execute("SELECT username FROM profiles").fetchall()
    return sorted((row["username"] for row in rows), key=lambda name: (name.casefold(), name))


def build_combined_preview(recap, *, profile_id, season, selection=None):
    """Prepend demo/provisional openings without mutating results or awards."""
    saga = recap["seasonSaga"]
    provisional = selection is None and not recap["finalized"]
    controls = {
        "selection": selection or "results",
        "provisional": provisional,
        "status": (
            "ANIMATION DEMO · NO AWARD GRANTED" if selection else
            "CURRENT LEADERS · RESULTS NOT FINAL" if provisional else
            "OFFICIAL CHAMPIONSHIPS · FULL SEASON REWIND"
        ),
        "options": [{"key": "results", "label": "Player's championships"}]
        + [{"key": "all", "label": "All five champions (demo)"}]
        + [{"key": key, "label": label + " (demo)"} for key, label, _, _ in CHOICES],
    }
    # The real Saga already includes every verified official title once.
    if not selection and recap["finalized"]:
        return saga, controls

    opening = []
    if selection:
        opening = build_champion_preview(selection, recap["username"])["beats"]
    else:
        snapshot = preview_season_championships(season["id"])
        for key, _, code, _ in CHOICES:
            winners = snapshot["winners"].get(code, [])
            if not any(int(w["profile_id"]) == int(profile_id) for w in winners):
                continue
            scenes = build_champion_preview(key, recap["username"])["beats"]
            for scene in scenes:
                scene["visual"] = {
                    **scene["visual"], "provisional": True, "shared": len(winners) > 1,
                }
                scene["eyebrow"] = "CURRENT LEADER PREVIEW"
                scene["description"] = "Current standings preview; championship results are not finalized."
                scene["evidence"] = (
                    "Read-only championship preview. All tied highest positive scores share the lead. "
                    "No award is created; final results require administrator approval."
                )
                if scene["kind"] == "winner":
                    scene["headline"] = scene["headline"].replace("CHAMPION", "LEADER")
            opening.extend(scenes)
    if not opening:
        return saga, controls

    # Keep all analytics, badge collections and the closing chapters intact.
    rest = [b for b in saga["beats"] if b["kind"] not in ("winner", "winner_badge", "welcome", "season_podium", "season_game_master")]
    beats = opening + rest
    return {
        **saga, "beats": beats, "count": len(beats), "demo": True,
        "method": "Staff-only championship preview followed by the player's real season Rewind.",
    }, controls

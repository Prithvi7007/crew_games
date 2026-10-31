"""Pure public honor facts from approved winners and cutoff-scoped season totals."""
from app.badges import BADGES_BY_CODE

GAME_MASTERS = (
    ("mystery", "Mystery Monday", "season_mystery_master"),
    ("trivia", "Trivia Tuesday", "season_trivia_master"),
    ("word", "Wordle Wednesday", "season_wordle_master"),
    ("tick_tock", "Tick-Tock Thursday", "season_tick_tock_master"),
)


def build_honors_visuals(points, names, official_winners, *, viewer_id):
    if not official_winners.get("season_champion"):
        return {"podium": [], "masters": []}
    frozen_names = {
        int(w["profile_id"]): w["username"]
        for winners in official_winners.values() for w in winners if w.get("username")
    }

    def name(pid):
        return frozen_names.get(pid, names.get(pid, "Another player"))

    ordered = sorted(
        ((int(pid), int(total)) for pid, total in points.items() if total > 0),
        key=lambda item: (-item[1], name(item[0]).casefold(), item[0]),
    )
    podium = []
    previous, place = None, 0
    for index, (pid, total) in enumerate(ordered, 1):
        if total != previous:
            place = index
            previous = total
        if place > 3:
            break
        if not podium or podium[-1]["place"] != place:
            podium.append({"place": place, "points": total, "players": []})
        podium[-1]["players"].append({
            "profileId": pid, "name": name(pid), "you": pid == int(viewer_id),
        })

    masters = []
    for game, label, code in GAME_MASTERS:
        winners = [
            {"profileId": int(w["profile_id"]), "name": name(int(w["profile_id"])),
             "points": int(w["points"])}
            for w in official_winners.get(code, []) if int(w.get("points", 0)) > 0
        ]
        if not winners:
            continue
        badge = BADGES_BY_CODE[code]
        masters.append({
            "gameKey": game, "gameName": label, "winners": winners,
            "badge": {"code": badge.code, "name": badge.name, "rarity": badge.rarity,
                      "gameKey": game, "vertical": badge.vertical},
        })
    return {"podium": podium, "masters": masters}

"""Pure animation demos; never qualify, finalize, or persist championship awards."""
from app.badges import BADGES_BY_CODE
from app.rewind_saga import GAME_TITLES, beat

CHOICES = (
    ("season", "Season champion", "season_champion", None),
    ("trivia", "Trivia champion", "season_trivia_master", "trivia"),
    ("word", "Wordle champion", "season_wordle_master", "word"),
    ("mystery", "Mystery champion", "season_mystery_master", "mystery"),
    ("tick_tock", "Tick-Tock champion", "season_tick_tock_master", "tick_tock"),
)
CHAMPION_PREVIEW_SELECTIONS = frozenset({"all", *(choice[0] for choice in CHOICES)})


def build_champion_preview(selection, player):
    """Return the real winner/badge scene shapes with explicit demo evidence."""
    if selection not in CHAMPION_PREVIEW_SELECTIONS:
        raise ValueError("Unknown champion animation preview")
    beats = []
    evidence = "Animation demo only. No championship result or badge award is created."
    for key, label, code, game in CHOICES:
        if selection != "all" and key != selection:
            continue
        badge = BADGES_BY_CODE[code]
        beats.append(beat(
            "winner", "CHAMPION ANIMATION PREVIEW", GAME_TITLES[code], "01",
            label + " animation preview.", evidence,
            {"badgeCode": code, "gameKey": game, "shared": False, "demo": True},
        ))
        beats.append(beat(
            "winner_badge", "BADGE ANIMATION PREVIEW", badge.name, "S01",
            "Preview of the championship badge reveal.", evidence,
            {"badge": {"code": badge.code, "name": badge.name,
                       "rarity": badge.rarity, "gameKey": game,
                       "vertical": badge.vertical}, "demo": True},
        ))
    return {
        "version": 3, "preview": True, "demo": True, "player": player,
        "beats": beats, "count": len(beats), "method": evidence,
        "championPreview": {
            "selection": selection,
            "options": [{"key": "all", "label": "All five champions"}]
            + [{"key": key, "label": label} for key, label, _, _ in CHOICES],
        },
    }

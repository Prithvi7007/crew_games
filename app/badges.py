"""Season-scoped CREW badge catalog and deterministic qualification rules.

Pure functions in this module never award points or write to the database.
PR1 intentionally does not hook badge evaluation into game routes.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True)
class Badge:
    code: str
    name: str
    vertical: str
    rarity: str
    game_key: str | None = None


# The public catalog is frozen at 21 definitions for V1.
BADGES = (
    Badge("case_closed", "Case Closed", "game_mastery", "common", "mystery"),
    Badge("sharp_instincts", "Sharp Instincts", "game_mastery", "rare", "mystery"),
    Badge("mind_reader", "Mind Reader", "game_mastery", "epic", "mystery"),
    Badge("sharp_shooter", "Sharp Shooter", "game_mastery", "common", "trivia"),
    Badge("brainiac", "Brainiac", "game_mastery", "rare", "trivia"),
    Badge("flawless_victory", "Flawless Victory", "game_mastery", "epic", "trivia"),
    Badge("word_wizard", "Word Wizard", "game_mastery", "common", "word"),
    Badge("word_ninja", "Word Ninja", "game_mastery", "rare", "word"),
    Badge("one_shot_wonder", "One-Shot Wonder", "game_mastery", "legendary", "word"),
    Badge("close_call", "Close Call", "game_mastery", "common", "tick_tock"),
    Badge("precision_pro", "Precision Pro", "game_mastery", "rare", "tick_tock"),
    Badge("human_stopwatch", "Human Stopwatch", "game_mastery", "epic", "tick_tock"),
    Badge("season_champion", "Season Champion", "leaderboard", "legendary"),
    Badge("season_trivia_master", "Season Trivia Master", "leaderboard", "epic"),
    Badge("season_wordle_master", "Season Wordle Master", "leaderboard", "epic"),
    Badge("season_mystery_master", "Season Mystery Master", "leaderboard", "epic"),
    Badge("season_tick_tock_master", "Season Tick-Tock Master", "leaderboard", "epic"),
    Badge("high_roller", "High Roller", "leaderboard", "epic"),
    Badge("unicorn", "Unicorn", "secret", "legendary"),
    Badge("badge_hunter", "Badge Hunter", "collection", "epic"),
    Badge("crew_legend", "CREW Legend", "collection", "legendary"),
)
BADGES_BY_CODE = {badge.code: badge for badge in BADGES}
GAME_KEYS = frozenset(("mystery", "trivia", "word", "tick_tock"))
COLLECTION_CODES = frozenset(("badge_hunter", "crew_legend"))
CHAMPIONSHIP_CODES = frozenset((
    "season_champion", "season_trivia_master", "season_wordle_master",
    "season_mystery_master", "season_tick_tock_master",
))


def _items(value):
    """Read saved JSON lists from attempt rows or already-deserialized states."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    return value if isinstance(value, list) else []


def _bounded_int(value, minimum, maximum):
    if isinstance(value, bool):
        return None
    try:
        integer = int(value)
    except (ValueError, TypeError):
        return None
    return integer if minimum <= integer <= maximum and str(value).strip() == str(integer) else None


def evaluate_game_badges(game_key: str, attempt: Mapping) -> frozenset[str]:
    """Evaluate a completed saved attempt, including catch-up/archived attempts.

    Callers must pass stored attempt state, never untrusted browser values.
    The game date determines the season when awards are persisted.
    """
    if game_key not in GAME_KEYS:
        raise ValueError("Unknown CREW game")
    if not attempt.get("completed"):
        return frozenset()

    earned = set()
    if game_key == "mystery":
        clues = _bounded_int(attempt.get("revealed_count"), 1, 4)
        if attempt.get("won") and clues is not None:
            if clues <= 3:
                earned.add("case_closed")
            if clues <= 2:
                earned.add("sharp_instincts")
            if clues == 1:
                earned.add("mind_reader")
    elif game_key == "trivia":
        answers = _items(attempt.get("answers", attempt.get("answers_json")))
        if len(answers) == 10 and all(isinstance(answer, dict) for answer in answers):
            count = sum(answer.get("correct") is True or answer.get("correct") == 1 for answer in answers)
            if count >= 8:
                earned.add("sharp_shooter")
            if count >= 9:
                earned.add("brainiac")
            if count == 10:
                earned.add("flawless_victory")
    elif game_key == "word":
        guesses = _items(attempt.get("guesses", attempt.get("guesses_json")))
        count = len(guesses)
        if attempt.get("won") and 1 <= count <= 6:
            if count <= 4:
                earned.add("word_wizard")
            if count <= 3:
                earned.add("word_ninja")
            if count == 1:
                earned.add("one_shot_wonder")
    elif game_key == "tick_tock":
        try:
            difference = Decimal(str(attempt.get("difference_seconds", attempt.get("difference"))))
        except (InvalidOperation, ValueError):
            difference = Decimal("NaN")
        if difference.is_finite() and difference >= 0:
            if difference <= Decimal("1.00"):
                earned.add("close_call")
            if difference <= Decimal("0.25"):
                earned.add("precision_pro")
            if difference <= Decimal("0.10"):
                earned.add("human_stopwatch")
    return frozenset(earned)


def evaluate_week_badges(scores_by_game: Mapping[str, int]) -> frozenset[str]:
    """Evaluate four completed games scheduled in the same CREW week/season."""
    if set(scores_by_game) != GAME_KEYS:
        return frozenset()
    scores = tuple(scores_by_game[key] for key in sorted(GAME_KEYS))
    if any(type(score) is not int or not (0 <= score <= 100) for score in scores):
        return frozenset()
    points = sum(scores)
    result = set()
    if points >= 350:
        result.add("high_roller")
    if points == 400:
        result.add("unicorn")
    return frozenset(result)


def evaluate_collection_badges(unlocked_codes) -> frozenset[str]:
    """Count distinct, valid non-collection badge types within ONE season."""
    eligible = set(unlocked_codes) & (BADGES_BY_CODE.keys() - COLLECTION_CODES)
    result = set()
    if len(eligible) >= 10:
        result.add("badge_hunter")
    if len(eligible) >= 15:
        result.add("crew_legend")
    return frozenset(result)

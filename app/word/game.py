from collections import Counter
from datetime import date

from app.db import get_db, get_game_content
from app.schedule import crew_today


SOLUTIONS = (
    "WORLD", "MAGIC", "QUEST", "DREAM", "LIGHT", "STORY", "BRAVE", "SMILE",
    "EARTH", "RIDER", "PARKS", "GLOBE", "TRAIN", "WATER", "MUSIC", "SPARK",
    "STAGE", "CROWN", "NIGHT", "RIVER", "OCEAN", "POWER", "ROBOT", "UNITY",
    "HAPPY", "LAUGH", "MOVIE", "SCENE", "SOUND", "ADORE", "SHINE", "STARS",
)

# CREW uses a broad English guess dictionary, while the daily answer pool stays
# intentionally curated. This mirrors the common Wordle-style split between
# "valid guesses" and "possible answers" without shipping the answer list to
# the browser. The web2 source comes from the MIT-licensed `english-words` package.
from functools import lru_cache
from english_words import get_english_words_set


@lru_cache(maxsize=1)
def get_allowed_words():
    # In the Web2 source, ordinary dictionary entries are lowercase while proper
    # nouns are capitalized. Keep lowercase alphabetic five-letter entries so
    # normal inflections/plurals such as CARTS are accepted without admitting
    # proper names.
    web2_words = get_english_words_set(["web2"])
    allowed = {
        word.upper()
        for word in web2_words
        if len(word) == 5 and word.isalpha() and word == word.lower()
    }
    return allowed.union(SOLUTIONS)


POINTS_BY_GUESS = {1: 100, 2: 80, 3: 65, 4: 50, 5: 40, 6: 30}


def get_daily_solution(game_date=None):
    game_date = game_date or crew_today()
    day_key = game_date.isoformat()
    scheduled = get_game_content("word", day_key, published_only=True)
    if scheduled:
        solution = str(scheduled["content"].get("solution") or "").strip().upper()
        if len(solution) == 5 and solution.isalpha():
            return solution
    db = get_db()
    row = db.execute(
        "SELECT solution FROM word_games WHERE game_date = ?", (day_key,)
    ).fetchone()
    if row:
        return row["solution"]

    # Stable date-based selection for the prototype; storing it keeps the answer fixed.
    index = game_date.toordinal() % len(SOLUTIONS)
    solution = SOLUTIONS[index]
    db.execute(
        "INSERT INTO word_games (game_date, solution) VALUES (?, ?)",
        (day_key, solution),
    )
    db.commit()
    return solution


def validate_guess(guess, game_date=None):
    guess = (guess or "").strip().upper()
    if len(guess) != 5 or not guess.isalpha():
        return False, "Enter a five-letter word."
    if guess not in get_allowed_words() and guess != get_daily_solution(game_date):
        return False, "That word isn't in the CREW dictionary."
    return True, guess


def evaluate_guess(guess, solution):
    """Evaluate duplicates correctly using exact-match then remaining-letter passes."""
    guess = guess.upper()
    solution = solution.upper()
    states = ["absent"] * 5
    remaining = Counter()

    for index, (letter, target) in enumerate(zip(guess, solution)):
        if letter == target:
            states[index] = "correct"
        else:
            remaining[target] += 1

    for index, letter in enumerate(guess):
        if states[index] == "correct":
            continue
        if remaining[letter] > 0:
            states[index] = "present"
            remaining[letter] -= 1

    return [
        {"letter": letter, "state": state}
        for letter, state in zip(guess, states)
    ]


def score_for_result(guess_count, won):
    return POINTS_BY_GUESS.get(guess_count, 0) if won else 10

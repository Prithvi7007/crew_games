from datetime import date, timedelta


GAME_DEFINITIONS = (
    {
        "key": "mystery",
        "day": "Monday",
        "title": "Mystery Monday",
        "short_title": "Mystery",
        "weekday": 0,
        "endpoint": "mystery.play",
        "description": "Solve a mystery from progressively easier clues.",
        "points": 100,
        "glyph": "?",
    },
    {
        "key": "trivia",
        "day": "Tuesday",
        "title": "Trivia Tuesday",
        "short_title": "Trivia",
        "weekday": 1,
        "endpoint": "trivia.play",
        "description": "Ten questions. One daily CREW challenge.",
        "points": 100,
        "glyph": "✦",
    },
    {
        "key": "word",
        "day": "Wednesday",
        "title": "Wordle Wednesday",
        "short_title": "Wordle",
        "weekday": 2,
        "endpoint": "word.play",
        "description": "One shared five-letter puzzle with six attempts.",
        "points": 100,
        "glyph": "W",
    },
    {
        "key": "tick_tock",
        "day": "Thursday",
        "title": "Tick-Tock Thursday",
        "short_title": "Tick-Tock",
        "weekday": 3,
        "endpoint": "tick_tock.play",
        "description": "Stop the hidden timer as close to the target as possible.",
        "points": 100,
        "glyph": "◷",
    },
)


def get_week_start(day=None):
    day = day or date.today()
    return day - timedelta(days=day.weekday())


def get_game_definition(game_key):
    return next(game for game in GAME_DEFINITIONS if game["key"] == game_key)


def get_game_date(game_key, reference_day=None):
    reference_day = reference_day or date.today()
    game = get_game_definition(game_key)
    return get_week_start(reference_day) + timedelta(days=game["weekday"])


def previous_scheduled_game_day(game_day):
    """Return the previous CREW game day, skipping Friday through Sunday."""
    weekday = game_day.weekday()
    if weekday in (1, 2, 3):
        return game_day - timedelta(days=1)
    if weekday == 0:
        return game_day - timedelta(days=3)

    cursor = game_day - timedelta(days=1)
    while cursor.weekday() > 3:
        cursor -= timedelta(days=1)
    return cursor


def next_scheduled_game_day(day=None):
    day = day or date.today()
    cursor = day
    for _ in range(8):
        if cursor.weekday() <= 3 and cursor >= day:
            return cursor
        cursor += timedelta(days=1)
    return cursor

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


CREW_TIMEZONE = os.getenv("CREW_TIMEZONE", "America/New_York")


def crew_today():
    return datetime.now(ZoneInfo(CREW_TIMEZONE)).date()


# CREW production archive begins with the original soft-launch history.
ARCHIVE_START_DATE = date(2026, 9, 7)

# The curated CREW season/question-bank launch starts Monday, September 21.
# This is WEEK 01 in the player-facing experience.
CREW_WEEK_ONE_DATE = date(2026, 9, 21)


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
    day = day or crew_today()
    return day - timedelta(days=day.weekday())


def get_crew_week_number(day=None):
    # Week 01 begins on 2026-09-21, when the curated question bank launches.
    # Dates before that are preseason and return 0.
    day = day or crew_today()
    week_start = get_week_start(day)
    if week_start < CREW_WEEK_ONE_DATE:
        return 0
    return ((week_start - CREW_WEEK_ONE_DATE).days // 7) + 1


def get_game_definition(game_key):
    return next(game for game in GAME_DEFINITIONS if game["key"] == game_key)


def get_game_date(game_key, reference_day=None):
    reference_day = reference_day or crew_today()
    game = get_game_definition(game_key)
    return get_week_start(reference_day) + timedelta(days=game["weekday"])


def previous_scheduled_game_day(game_day):
    """Return the previous CREW game day, skipping Friday through Sunday."""
    weekday = game_day.weekday()
    if weekday in (1, 2, 3):
        return game_day - timedelta(days=1)
    if weekday == 0:
        return game_day - timedelta(days=4)

    cursor = game_day - timedelta(days=1)
    while cursor.weekday() > 3:
        cursor -= timedelta(days=1)
    return cursor


def next_scheduled_game_day(day=None):
    day = day or crew_today()
    cursor = day
    for _ in range(8):
        if cursor.weekday() <= 3 and cursor >= day:
            return cursor
        cursor += timedelta(days=1)
    return cursor


def parse_game_day(game_key, raw_date=None, today=None):
    """Resolve an optional YYYY-MM-DD archive date and ensure it matches the game's weekday."""
    today = today or crew_today()
    if not raw_date:
        return get_game_date(game_key, today)
    try:
        candidate = date.fromisoformat(raw_date)
    except (TypeError, ValueError):
        return get_game_date(game_key, today)
    definition = get_game_definition(game_key)
    if candidate.weekday() != definition["weekday"]:
        return get_game_date(game_key, today)
    return candidate


def game_is_playable(game_day, today=None):
    today = today or crew_today()
    return game_day <= today


def game_is_competitive(game_day, today=None):
    """Return whether this completion is timely enough to count toward streaks."""
    today = today or crew_today()
    return (
        today.weekday() <= 3
        and game_day <= today
        and get_week_start(game_day) == get_week_start(today)
    )


def game_is_archive(game_day, today=None):
    """A challenge is an archive play when it belongs to an earlier CREW week."""
    today = today or crew_today()
    return game_day < get_week_start(today)


def game_is_in_archive(game_day):
    return game_day >= ARCHIVE_START_DATE

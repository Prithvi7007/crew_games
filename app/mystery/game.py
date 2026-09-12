import re

from app.db import get_game_content


PUZZLES = (
    {
        "theme": "Jurassic World",
        "answer": "JURASSIC WORLD",
        "accepted": {"JURASSIC WORLD", "JURASSICWORLD"},
        "clues": (
            "This world asks what happens when wonder, science and ambition collide.",
            "Its stars have been gone for millions of years, but they never stay quiet for long.",
            "A fictional park sits at the center of the adventure.",
            "Velociraptors and a T. rex are unmistakable residents.",
            "Name the dinosaur-filled franchise whose title begins with “Jurassic.”",
        ),
    },
    {
        "theme": "Minions",
        "answer": "MINIONS",
        "accepted": {"MINION", "MINIONS"},
        "clues": (
            "This CREW is famous for chaotic teamwork and an unusual vocabulary.",
            "Their loyalty tends to follow whoever looks most villainous at the time.",
            "Bananas are a recurring obsession.",
            "Blue overalls are part of the uniform.",
            "Name the small yellow characters from Despicable Me.",
        ),
    },
    {
        "theme": "DreamWorks",
        "answer": "SHREK",
        "accepted": {"SHREK"},
        "clues": (
            "This unlikely hero would rather keep visitors away from home.",
            "A talkative best friend makes solitude nearly impossible.",
            "Fairy-tale characters repeatedly complicate the journey.",
            "The hero lives in a swamp.",
            "Name the green ogre at the center of the DreamWorks story.",
        ),
    },
    {
        "theme": "TRANSFORMERS",
        "answer": "OPTIMUS PRIME",
        "accepted": {"OPTIMUS PRIME", "OPTIMUSPRIME", "OPTIMUS"},
        "clues": (
            "This leader is known as much for conviction as for power.",
            "The character belongs to a conflict between two factions from Cybertron.",
            "He leads the Autobots.",
            "His alternate form is famously a truck.",
            "Name the red-and-blue Autobot leader.",
        ),
    },
)


SCORE_BY_CLUES = {1: 100, 2: 80, 3: 60, 4: 40, 5: 20}


def get_puzzle(game_day):
    scheduled = get_game_content("mystery", game_day.isoformat(), published_only=True)
    if scheduled:
        content = scheduled["content"]
        clues = tuple(content.get("clues") or ())
        answer = str(content.get("answer") or "").strip()
        accepted = {str(item).strip() for item in (content.get("accepted") or []) if str(item).strip()}
        if answer and len(clues) == 5:
            accepted.add(answer)
            return {
                "theme": scheduled["theme_label"],
                "answer": answer,
                "accepted": accepted,
                "clues": clues,
            }
    return PUZZLES[game_day.toordinal() % len(PUZZLES)]


def normalize_answer(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def is_correct_answer(value, puzzle):
    normalized = normalize_answer(value)
    return any(normalized == normalize_answer(answer) for answer in puzzle["accepted"])


def score_for_clues(revealed_count):
    return SCORE_BY_CLUES.get(max(1, min(5, revealed_count)), 10)

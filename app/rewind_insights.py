"""Explainable, cutoff-scoped CREW Rewind play-style analytics.

Only accepts completion rows supplied by season_rewind.py. It must never
issue queries or widen the finalized championship scoring window.
"""
from collections import defaultdict
from datetime import date

from app.schedule import get_week_start


_GAME_NAMES = {
    "mystery": "Mystery Monday",
    "trivia": "Trivia Tuesday",
    "word": "Wordle Wednesday",
    "tick_tock": "Tick-Tock Thursday",
}


def build_rewind_insights(mine, completions, *, profile_id, season_start,
                          weeks_total, signature, rank, participants, points,
                          benchmark_profile_ids=None):
    """Return descriptive evidence, not predictions or invented precision."""
    me = int(profile_id)
    peer_ids = None if benchmark_profile_ids is None else set(benchmark_profile_ids)
    week_zero = get_week_start(season_start)
    half = max(1, (int(weeks_total) + 1) // 2)
    first, second = [], []
    played_weeks = set()
    by_game = defaultdict(list)
    peer_by_game = defaultdict(lambda: defaultdict(list))
    best = None

    for row in completions:
        pid, game = int(row["profile_id"]), row["game_key"]
        if pid != me:
            if peer_ids is None or pid in peer_ids:
                peer_by_game[game][pid].append(int(row["score"]))
            continue

        score = int(row["score"])
        day = date.fromisoformat(str(row["game_date"]))
        week = (get_week_start(day) - week_zero).days // 7 + 1
        played_weeks.add(week)
        by_game[game].append(score)
        (first if week <= half else second).append(score)
        if best is None or score > best["score"]:
            best = {
                "score": score, "game": _GAME_NAMES.get(game, game),
                "week": week,
            }

    scores = [score for values in by_game.values() for score in values]
    average = round(sum(scores) / len(scores)) if scores else None
    streak = current = 0
    for week in range(1, int(weeks_total) + 1):
        current = current + 1 if week in played_weeks else 0
        streak = max(streak, current)

    momentum = None
    if len(first) >= 2 and len(second) >= 2:
        start_average = round(sum(first) / len(first))
        end_average = round(sum(second) / len(second))
        change = end_average - start_average
        momentum = {
            "firstAverage": start_average,
            "secondAverage": end_average,
            "change": change,
            "direction": "up" if change >= 8 else "down" if change <= -8 else "steady",
        }

    peer_comparison = None
    if signature and len(by_game[signature["key"]]) >= 2:
        peer_means = [
            sum(values) / len(values)
            for values in peer_by_game[signature["key"]].values()
            if values
        ]
        # Avoid making a small peer sample look like the whole CREW.
        if len(peer_means) >= 3:
            cohort_average = round(sum(peer_means) / len(peer_means))
            personal_average = round(sum(by_game[signature["key"]]) /
                                     len(by_game[signature["key"]]))
            peer_comparison = {
                "game": signature["name"],
                "yourAverage": personal_average,
                "crewAverage": cohort_average,
                "difference": personal_average - cohort_average,
                "playersCompared": len(peer_means),
            }

    kinds = len(by_game)
    if not scores:
        title = "THE NEXT CHAPTER"
        evidence = "Your Season 01 play style is still yours to discover."
    elif kinds == 4:
        title = "THE ALL-ROUNDER"
        evidence = "You took on all four CREW game types."
    elif momentum and momentum["direction"] == "up" and momentum["change"] >= 12:
        title = "THE FINISHER"
        evidence = ("Your later-season games averaged "
                    f'{momentum["change"]} more points per game.')
    elif (signature and kinds >= 2 and signature["played"] >= 2
          and average is not None and signature["average"] - average >= 12):
        title = "THE SPECIALIST"
        evidence = (f'{signature["name"]} was your edge: '
                    f'{signature["average"] - average} points above '
                    'your personal game average.')
    elif streak >= 3:
        title = "THE MAINSTAY"
        evidence = f"You completed games from {streak} consecutive season weeks."
    elif kinds >= 2:
        title = "THE EXPLORER"
        evidence = f"You tested your skills across {kinds} different games."
    else:
        title = "THE CHALLENGER"
        evidence = f"You took on {_GAME_NAMES.get(next(iter(by_game)), 'CREW Games')}."

    # A strict comparison ignores equal scores; tied people were not outscored.
    # A one-player leaderboard should not be portrayed as a percentile.
    outpaced = None
    if scores and rank is not None and participants > 1:
        opponents = defaultdict(int)
        for row in completions:
            opponents[int(row["profile_id"])] += int(row["score"])
        outpaced_count = sum(
            1 for pid, total in opponents.items()
            if pid != me and total < points
        )
        outpaced = round(100 * outpaced_count / (participants - 1))

    return {
        "averageScore": average,
        "gamesTried": kinds,
        "longestWeeklyStreak": streak,
        "highestGame": best,
        "momentum": momentum,
        "peerComparison": peer_comparison,
        "outpacedPercent": outpaced,
        "playStyle": {"title": title, "evidence": evidence},
    }

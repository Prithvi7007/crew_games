"""Compose a personalized cinematic Rewind from cutoff-scoped evidence.

The film uses the same facts as the read-only analyst report. It never changes
the ranking or generates claims when there is no eligible comparative sample.
All variation follows evidence, not names or manually assigned personas.
"""
from collections import defaultdict
from datetime import date

from app.schedule import get_week_start
from app.rewind_analytics import GAMES


def _beat(kind, eyebrow, headline, metric, description, evidence, visual=None):
    return {
        "kind": kind, "eyebrow": eyebrow, "headline": headline,
        "metric": str(metric), "description": description,
        "evidence": evidence, "visual": visual or {},
    }


def _week_for(day, start):
    return (get_week_start(date.fromisoformat(str(day))) -
            get_week_start(start)).days // 7 + 1


def _closest_rival_data(rows, me, start, weeks_total, names):
    """Official-score-candidate nearest rival, with a real weekly trail."""
    totals, counts = defaultdict(int), defaultdict(int)
    by_game = defaultdict(lambda: defaultdict(int))
    by_week = defaultdict(lambda: defaultdict(int))
    for row in rows:
        game = row["game_key"]
        if game not in GAMES:
            continue
        week = _week_for(row["game_date"], start)
        if not 1 <= week <= weeks_total:
            continue
        pid, points = int(row["profile_id"]), int(row["score"])
        totals[pid] += points
        counts[pid] += 1
        by_game[pid][game] += points
        by_week[pid][week] += points
    others = [
        (abs(totals[me] - total), abs(counts[me] - counts[pid]), pid)
        for pid, total in totals.items() if pid != me and total > 0
    ]
    if len(others) < 3 or totals[me] <= 0:
        return None
    _, _, rival = min(others)
    differences = [
        {"game": game, "name": name,
         "difference": by_game[me][game] - by_game[rival][game],
         "mine": by_game[me][game], "rival": by_game[rival][game]}
        for game, name in GAMES.items()
    ]
    my_running = other_running = 0
    trail = []
    for week in range(1, weeks_total + 1):
        my_running += by_week[me][week]
        other_running += by_week[rival][week]
        trail.append({
            "week": week, "mine": my_running, "rival": other_running,
            "difference": my_running - other_running,
        })
    return {
        "name": names.get(rival, "another player"),
        "myTotal": totals[me], "theirTotal": totals[rival],
        "gap": abs(totals[me] - totals[rival]),
        "difference": totals[me] - totals[rival],
        "games": differences, "weekly": trail,
    }


def build_rewind_story(recap, completions, *, profile_id, season_start,
                       weeks_total, profile_names):
    """One story engine for every player, including very sparse histories."""
    report = recap["analyticsStory"]
    cards = {item["key"]: item for item in report["cards"]}
    sample = report["sample"]
    username = recap["username"]
    game_count = sample["completedGames"]
    rival = (_closest_rival_data(completions, int(profile_id), season_start,
                                 weeks_total, profile_names)
             if "closest_rival" in cards else None)
    finalized = bool(recap["finalized"])
    status = "official final rank" if finalized else "current preview rank"
    ranked = recap["rank"]
    ranking = f"#{ranked} {status}" if ranked else "No ranked finish yet"

    # A close final margin can lead the film, but a large points difference
    # should not be sold as a nail-biter.
    narrow = bool(rival and rival["gap"] > 0 and
                  rival["gap"] <= max(25, round(rival["myTotal"] * .06)))
    if narrow:
        title = f"The {rival['gap']}-Point Finish"
        opener = (f"Only {rival['gap']} points separated you and "
                  f"{rival['name']}.")
        opening_metric = str(rival["gap"])
        motif = "rivalry"
    elif "pivotal_week" in cards:
        title = "The Week That Mattered"
        opener = cards["pivotal_week"]["story"]
        opening_metric = cards["pivotal_week"]["metric"]
        motif = "turning_point"
    elif "same_puzzle" in cards:
        title = "The Day You Stood Out"
        opener = cards["same_puzzle"]["story"]
        opening_metric = cards["same_puzzle"]["metric"]
        motif = "standout"
    elif "matched_momentum" in cards:
        title = "The Changing Pace"
        opener = cards["matched_momentum"]["story"]
        opening_metric = cards["matched_momentum"]["metric"]
        motif = "momentum"
    elif "relative_strength" in cards:
        title = "Your Unexpected Edge"
        opener = cards["relative_strength"]["story"]
        opening_metric = cards["relative_strength"]["metric"]
        motif = "strength"
    elif "consistency" in cards:
        title = "The Long Game"
        opener = cards["consistency"]["story"]
        opening_metric = cards["consistency"]["metric"]
        motif = "consistency"
    elif game_count:
        title = "The Games You Played"
        opener = (f"You completed {game_count} season "
                  f"{'game' if game_count == 1 else 'games'}. "
                  "Your story is still taking shape.")
        opening_metric = str(game_count)
        motif = "participation"
    else:
        title = "The Next Chapter"
        opener = ("No completed games in this season yet. "
                  "There is nothing to compare, and we won't invent a story.")
        opening_metric = "01"
        motif = "unplayed"

    beats = [_beat(
        "opening", "SEASON 01 / YOUR UNTOLD STORY", title, opening_metric,
        opener, f"{game_count} completed games · {ranking}",
        {"motif": motif, "total": recap["points"]},
    )]

    if rival:
        gap = rival["gap"]
        direction = ("ahead of" if rival["difference"] > 0 else
                     "behind" if rival["difference"] < 0 else "tied with")
        suffix = ("point" if gap == 1 else "points")
        beats.append(_beat(
            "rivalry", "THE FINISH LINE", f"Meet {rival['name']}.",
            f"{gap} {suffix}",
            f"You finished {gap} {suffix} {direction} {rival['name']} "
            "in the season points totals.",
            "Final cumulative totals, not a claim of a live head-to-head.",
            {"rival": rival},
        ))
        # Reveal the biggest positive game contribution *relative to this
        # specific rival*, and the offset across other games. This explains
        # a close finish without claiming a higher skill at that game.
        edges = [g for g in rival["games"] if g["difference"] > 0]
        if edges:
            strongest = max(edges, key=lambda g: g["difference"])
            remainder = rival["difference"] - strongest["difference"]
            if remainder < 0 and rival["difference"] > 0:
                beats.append(_beat(
                    "swing", "THE SURPRISE", f"{strongest['name']} changed the math.",
                    f"+{strongest['difference']}",
                    f"You earned {strongest['difference']} more total "
                    f"{strongest['name']} points than {rival['name']}. "
                    f"Across the other three games, {rival['name']} "
                    f"earned {abs(remainder)} more points. "
                    f"Your final advantage: {rival['difference']}.",
                    "Points contributed by game across the entire season; "
                    "not a same-attempt skill comparison.",
                    {"game": strongest["name"], "edge": strongest["difference"],
                     "other": remainder, "net": rival["difference"]},
                ))
    for key, kind in [
        ("pivotal_week", "pivot"), ("relative_strength", "strength"),
        ("same_puzzle", "standout"), ("matched_momentum", "momentum"),
        ("consistency", "consistency"),
    ]:
        if key not in cards:
            continue
        card = cards[key]
        visual = {"sourceKey": key}
        if key == "consistency":
            visual["weeksActive"] = sample["weeksActive"]
            visual["weeksTotal"] = weeks_total
        if key == "pivotal_week":
            visual["currentRank"] = ranked
        beats.append(_beat(
            kind, card["label"], card["title"], card["metric"],
            card["story"], card["evidence"], visual,
        ))

    # Avoid lengthy, repetitive films. Each beat needs one *different*
    # discovery, not an animated restatement of the same totals.
    beats = beats[:7]
    beats.append(_beat(
        "ending", "YOUR SEASON / IN FULL", f"That was your story, {username}.",
        str(game_count),
        (f"{game_count} completed games across "
         f"{sample['weeksActive']} of {weeks_total} weeks. "
         "The details are what made this season yours."),
        ranking, {"motif": motif, "total": recap["points"]},
    ))
    return {
        "version": 2, "title": title, "motif": motif,
        "preview": not finalized, "player": username,
        "beats": beats, "count": len(beats),
        "method": ("All comparisons use the cutoff-scoped Season 01 "
                   "completion records. Hypothetical ranks are not historic "
                   "ranks. A player may have fewer beats if the evidence "
                   "doesn't support a claim."),
    }

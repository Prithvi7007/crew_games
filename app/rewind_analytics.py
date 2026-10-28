"""Evidence-first retrospective: new discoveries from the exact Rewind cutoff rows.

This module accepts already-authorized season completions; it never queries the
database, changes rankings, or silently expands the championship score window.
Every claim supplies a human-readable calculation and sample-size evidence.
"""
from collections import defaultdict
from datetime import date
from statistics import mean, median

from app.schedule import get_week_start


GAMES = {
    "mystery": "Mystery",
    "trivia": "Trivia",
    "word": "Wordle",
    "tick_tock": "Tick-Tock",
}


def _card(key, label, title, metric, story, evidence, method):
    return {
        "key": key,
        "label": label,
        "title": title,
        "metric": str(metric),
        "story": story,
        "evidence": evidence,
        "method": method,
    }


def _place(totals, games_played, names, user_id):
    """The same tie-breaking rule as the official Season 01 leaderboard."""
    active = sorted(
        (pid for pid, points in totals.items() if points > 0),
        key=lambda pid: (-totals[pid], -games_played[pid],
                         names.get(pid, "").casefold(), pid),
    )
    return active.index(user_id) + 1 if user_id in active else None


def build_rewind_analytics(mine, completions, *, profile_id, season_start,
                           weeks_total, profile_names, rank):
    """Generate substantive, sampled stories; omit claims without enough data.

    Peer game comparisons are within the same game type and average *per
    player*, so somebody who played six rounds doesn't count six times as a
    peer. A 'what if' rank is an explicit counterfactual, not historic rank.
    """
    me = int(profile_id)
    first_monday = get_week_start(season_start)
    half = max(1, (int(weeks_total) + 1) // 2)
    own_by_game = defaultdict(list)
    by_player_game = defaultdict(lambda: defaultdict(list))
    event_players = defaultdict(dict)
    player_totals = defaultdict(int)
    player_counts = defaultdict(int)
    player_weeks = defaultdict(set)
    weekly_own = defaultdict(lambda: {"points": 0, "completed": 0})
    early_late = defaultdict(lambda: {"early": [], "late": []})

    for row in completions:
        pid = int(row["profile_id"])
        game = row["game_key"]
        if game not in GAMES:
            continue
        score = int(row["score"])
        day = date.fromisoformat(str(row["game_date"]))
        week = (get_week_start(day) - first_monday).days // 7 + 1
        if week < 1 or week > weeks_total:
            continue
        by_player_game[pid][game].append(score)
        event_players[(game, day.isoformat())][pid] = score
        player_totals[pid] += score
        player_counts[pid] += 1
        player_weeks[pid].add(week)
        if pid == me:
            own_by_game[game].append(score)
            weekly_own[week]["points"] += score
            weekly_own[week]["completed"] += 1
            early_late[game]["early" if week <= half else "late"].append(score)

    cards = []
    sample = {
        "completedGames": player_counts[me],
        "weeksActive": len(player_weeks[me]),
        "otherActivePlayers": len([pid for pid in player_counts if pid != me]),
    }

    # 1. One specific puzzle in which the player beat the same-task field.
    # Do not conflate a high score with winning without a peer comparison.
    standout = None
    for row in mine:
        game = row["game_key"]
        day = str(row["game_date"])
        peers = [score for pid, score in event_players[(game, day)].items()
                 if pid != me]
        if len(peers) < 3:
            continue
        score = int(row["score"])
        better = sum(score > other for other in peers)
        margin = score - median(peers)
        if better < 2 or margin <= 0:
            continue
        candidate = (better / len(peers), margin, better, len(peers), game, day, score)
        if standout is None or candidate[:2] > standout[:2]:
            standout = candidate
    if standout:
        _, margin, better, peers_count, game, day, score = standout
        cards.append(_card(
            "same_puzzle", "THE DAY YOU STOOD OUT",
            f"{GAMES[game]} was your moment.",
            f"{better} / {peers_count}",
            f"On {date.fromisoformat(day).strftime('%b %-d')}, you scored "
            f"{score} in {GAMES[game]} and outscored {better} of the "
            f"{peers_count} other players who completed that exact puzzle.",
            f"Your score was {margin:g} points above that puzzle's peer median.",
            "Same game, same puzzle date; compares one score per other player. "
            "Minimum three other players.",
        ))

    # 2. A hidden strength measured against the field *within* each game.
    benchmarks = []
    for game, scores in own_by_game.items():
        if len(scores) < 2:
            continue
        peers = [mean(games[game]) for pid, games in by_player_game.items()
                 if pid != me and games.get(game)]
        if len(peers) < 3:
            continue
        mine_avg = mean(scores)
        peer_avg = mean(peers)
        benchmarks.append((mine_avg - peer_avg, game, mine_avg, peer_avg,
                           len(scores), len(peers)))
    benchmarks = [entry for entry in benchmarks if abs(entry[0]) >= 5]
    if benchmarks:
        advantage, game, mine_avg, peer_avg, attempts, peers_count = max(benchmarks)
        direction = "above" if advantage > 0 else "below"
        cards.append(_card(
            "relative_strength", "YOUR HIDDEN STRENGTH",
            f"{GAMES[game]} was your strongest matchup.",
            f"{'+' if advantage > 0 else ''}{round(advantage)} pts",
            f"You averaged {round(mine_avg)} points per {GAMES[game]} game, "
            f"{abs(round(advantage))} points {direction} the other "
            f"players' average in that same game.",
            f"Based on {attempts} of your games and {peers_count} other "
            f"players; this was your best relative matchup among "
            f"{len(benchmarks)} comparable game types.",
            "Each competitor contributes one per-game average, regardless "
            "of number of attempts. No cross-game scoring comparison.",
        ))

    # 3. A season-changing week, as a *counterfactual*, not a claimed
    # historical leaderboard movement. Other players' scores are unchanged.
    positive_weeks = [(row["points"], -w, w, row["completed"])
                      for w, row in weekly_own.items() if row["points"] > 0]
    eligible_opponents = sum(pid != me and points > 0
                             for pid, points in player_totals.items())
    if (positive_weeks and rank is not None and len(player_weeks[me]) >= 2
            and eligible_opponents >= 3):
        points, _, best_week, count = max(positive_weeks)
        adjusted_points = dict(player_totals)
        adjusted_counts = dict(player_counts)
        adjusted_points[me] -= points
        adjusted_counts[me] -= count
        without = _place(adjusted_points, adjusted_counts, profile_names, me)
        if without is None or without > rank:
            movement = without - rank if without is not None else None
            cards.append(_card(
                "pivotal_week", "THE WEEK THAT MATTERED",
                f"Week {best_week} protected your place.",
                f"{'+' + str(movement) + ' places' if movement else 'Unranked'}",
                f"You earned {points} points in week {best_week}. Without "
                f"that one week, your rank would be "
                f"{'#' + str(without) if without else 'outside the ranked field'} "
                f"instead of #{rank}.",
                f"The what-if removes only your {count} game(s) and "
                "keeps every other player's season unchanged.",
                "Hypothetical final standings using official point, "
                "completion-count and username tie-breakers. This is not "
                "a historical week-by-week ranking.",
            ))

    # 4. The closest final rival in total *points*, not necessarily the
    # nearest official rank. Distinguish ties and count-based tie breaks.
    opponents = [(abs(player_totals[pid] - player_totals[me]), pid)
                 for pid in player_counts if pid != me and player_totals[pid] > 0]
    if opponents and player_totals[me] > 0:
        gap, opponent = min(opponents, key=lambda item: (
            item[0], abs(player_counts[item[1]] - player_counts[me]), item[1]))
        other_name = profile_names.get(opponent, "Another player")
        delta = player_totals[me] - player_totals[opponent]
        if delta == 0:
            story = (f"You and {other_name} finished on "
                     f"{player_totals[me]} points. Completion count and "
                     "the official tie-break rules determined your positions.")
        else:
            direction = "ahead of" if delta > 0 else "behind"
            story = (f"You finished {gap} points {direction} {other_name}. "
                     "That was your closest final points matchup.")
        # Which game accounted for the largest positive difference?
        differences = [(sum(own_by_game[game]) -
                        sum(by_player_game[opponent].get(game, [])), game)
                       for game in GAMES]
        best_gap, best_game = max(differences)
        evidence = (f"Your biggest points edge over {other_name} was "
                    f"{best_gap} in {GAMES[best_game]}."
                    if best_gap > 0 else
                    "The two totals include every completed game in the season.")
        cards.append(_card(
            "closest_rival", "THE CLOSEST RIVAL",
            f"{other_name} was closest to you.",
            f"{gap} pts apart", story, evidence,
            "Absolute gap in final season points, not a live head-to-head "
            "or historical rivalry.",
        ))

    # 5. Apples-to-apples improvement: compare only games played in
    # both halves. Demand two attempts in *each* half per game.
    paired = [(game, mean(halves["late"]) - mean(halves["early"]),
               len(halves["early"]), len(halves["late"]))
              for game, halves in early_late.items()
              if len(halves["early"]) >= 2 and len(halves["late"]) >= 2]
    if paired:
        change = mean(item[1] for item in paired)
        if abs(change) >= 8:
            direction = "improved" if change > 0 else "declined"
            labels = ", ".join(GAMES[item[0]] for item in paired)
            cards.append(_card(
                "matched_momentum", "YOUR REAL MOMENTUM",
                "The second half told a different story.",
                f"{'+' if change > 0 else ''}{round(change)} pts/game",
                f"Your average {direction} by {abs(round(change))} points "
                "per game in the second half, when comparing only "
                f"the same game types: {labels}.",
                f"{sum(r[2] for r in paired)} earlier and "
                f"{sum(r[3] for r in paired)} later completions "
                f"across {len(paired)} comparable game types.",
                "Mean of within-game changes, giving each comparable game "
                "type equal weight. Excludes games played only in one half.",
            ))

    # 6. Reliability compared with active peers; ties are not 'outpaced'.
    peer_weeks = [len(weeks) for pid, weeks in player_weeks.items() if pid != me]
    if len(peer_weeks) >= 3 and sample["weeksActive"] >= 2:
        beat = sum(sample["weeksActive"] > other for other in peer_weeks)
        if beat > 0:
            cards.append(_card(
                "consistency", "YOU KEPT SHOWING UP",
                "Consistency was part of your advantage.",
                f"{sample['weeksActive']} / {weeks_total} weeks",
                f"You earned points in {sample['weeksActive']} of the "
                f"{weeks_total} season weeks, more than {beat} of the "
                f"{len(peer_weeks)} other active players.",
                f"The other active players' median was "
                f"{median(peer_weeks):g} weeks.",
                "Participation compares distinct scheduled puzzle weeks. "
                "Tied players are not counted as beaten.",
            ))

    return {
        "version": 1,
        "sample": sample,
        "cards": cards[:6],
        "limitations": (
            "These findings describe completed, cutoff-eligible games. "
            "Missing plays are not inferred as failures; comparisons may "
            "be omitted when the sample is too small. The ranking what-if "
            "is not a historical position."
        ),
    }

"""Season 01 Saga: read-only, official-cutoff-scoped cinematic story evidence.

The achievement opening is backed ONLY by approved championship snapshots.
Other chapters use the exact same eligible completions as the legacy Rewind.
"""
from collections import defaultdict
from datetime import date

from app.badges import BADGES_BY_CODE, CHAMPIONSHIP_CODES
from app.schedule import get_week_start
from app.rewind_honors import build_honors_visuals

GAMES = (
    ("mystery", "Mystery Monday"),
    ("trivia", "Trivia Tuesday"),
    ("word", "Wordle Wednesday"),
    ("tick_tock", "Tick-Tock Thursday"),
)
GAME_LABELS = dict(GAMES)
TITLE_ORDER = (
    "season_champion", "season_trivia_master", "season_wordle_master",
    "season_mystery_master", "season_tick_tock_master",
)
GAME_TITLES = {
    "season_champion": "SEASON 01 CHAMPION",
    "season_trivia_master": "TRIVIA LEADER",
    "season_wordle_master": "WORDLE LEADER",
    "season_mystery_master": "MYSTERY LEADER",
    "season_tick_tock_master": "TICK-TOCK LEADER",
}
RARITY = {"legendary": 4, "epic": 3, "rare": 2, "common": 1}


def beat(kind, label, title, metric, description, evidence, visual=None):
    return {
        "kind": kind, "eyebrow": label, "headline": title,
        "metric": str(metric), "description": description, "evidence": evidence,
        "visual": visual or {},
    }


def build_season_saga(recap, rows, *, profile_id, season_start, weeks_total,
                      names, official_winners, awarded_codes, benchmark_profile_ids=None):
    """Personalize all nine conceptual acts; omit unsupported accolades."""
    me = int(profile_id)
    peer_ids = None if benchmark_profile_ids is None else set(benchmark_profile_ids)
    first = get_week_start(season_start)
    per_week = defaultdict(lambda: defaultdict(lambda: {"points": 0, "played": 0}))
    per_game = defaultdict(lambda: defaultdict(list))
    all_points = defaultdict(int)
    all_plays = defaultdict(int)
    for row in rows:
        game = row["game_key"]
        if game not in GAME_LABELS:
            continue
        pid = int(row["profile_id"])
        week = ((get_week_start(date.fromisoformat(str(row["game_date"]))) - first).days // 7) + 1
        if week < 1 or week > weeks_total:
            continue
        score = int(row["score"])
        per_week[week][pid]["points"] += score
        per_week[week][pid]["played"] += 1
        per_game[pid][game].append(score)
        all_points[pid] += score
        all_plays[pid] += 1

    chapters = []
    # 1. Championships: a claim needs the immutable finalization snapshot,
    # not a guessed rank, a current preview or even a manually granted badge.
    official_codes = [
        code for code in TITLE_ORDER
        if any(int(w["profile_id"]) == me for w in official_winners.get(code, []))
        and code in awarded_codes
    ]
    for code in official_codes:
        badge = BADGES_BY_CODE[code]
        title = GAME_TITLES[code]
        champions = official_winners[code]
        shared = len(champions) > 1
        game = (None if code == "season_champion"
                else next(key for key, _ in GAMES if code == {
                    "mystery": "season_mystery_master",
                    "trivia": "season_trivia_master",
                    "word": "season_wordle_master",
                    "tick_tock": "season_tick_tock_master",
                }[key]))
        chapters.append(beat(
            "winner", "YOUR MOMENT OF GLORY", title, "01",
            ("You earned the title alongside another leader." if shared else
             "The season's highest official total was yours."),
            "Award verified against the approved Season 01 championship winner snapshot.",
            {"badgeCode": code, "gameKey": game, "shared": shared},
        ))
        chapters.append(beat(
            "winner_badge", "A TITLE TO REMEMBER", badge.name, "S01",
            "An official CREW Season 01 championship badge, earned and preserved.",
            "Official season-specific championship badge verified against the finalization snapshot.",
            {"badge": {"code": badge.code, "name": badge.name,
                        "rarity": badge.rarity, "gameKey": game,
                        "vertical": badge.vertical}},
        ))
    if not official_codes:
        is_official_winner = any(
            int(w["profile_id"]) == me
            for winners in official_winners.values() for w in winners
        )
        if recap["finalized"] and not is_official_winner:
            honors = build_honors_visuals(all_points, names, official_winners, viewer_id=me)
            if honors["podium"]:
                chapters.append(beat(
                    "season_podium", "THE SEASON HONORS", "The Season 01 podium.",
                    "TOP 3", "The season's leading point totals. A moment for the CREW.",
                    "Positive cutoff-eligible season totals. Equal point totals share "
                    "a podium place; all ties within the Top 3 places are shown.",
                    {"podium": honors["podium"]},
                ))
            for master in honors["masters"]:
                chapters.append(beat(
                    "season_game_master", "THE GAME MASTERS", master["badge"]["name"],
                    "S01", "Meet the official season game master" +
                    ("s." if len(master["winners"]) > 1 else "."),
                    "Winner names and points come from the approved Season 01 "
                    "championship snapshot. Shared first places retain every winner.",
                    master,
                ))
        chapters.append(beat(
            "welcome", "CREW / SEASON 01", "Your season. Your story.", "01",
            "Every week had a story. This one belongs to you.",
            "All displayed results come from eligible Season 01 completions.",
            {"player": recap["username"]},
        ))

    # 2. Rank each weekly leaderboard by official points/completion/name rules,
    # then rank number of weekly top-three appearances across Season 01.
    podiums = defaultdict(list)
    weekly = []
    for week in range(1, weeks_total + 1):
        active = sorted(
            (pid for pid, data in per_week[week].items() if data["points"] > 0),
            key=lambda pid: (-per_week[week][pid]["points"],
                             -per_week[week][pid]["played"],
                             names.get(pid, "").casefold(), pid),
        )
        for pos, pid in enumerate(active[:3], 1):
            podiums[pid].append({"week": week, "place": pos,
                                "points": per_week[week][pid]["points"]})
        peer_totals = [
            data["points"] for pid, data in per_week[week].items()
            if pid != me and data["played"]
            and (peer_ids is None or pid in peer_ids)
        ]
        weekly.append({
            "week": week,
            "mine": per_week[week][me]["points"],
            "highest": per_week[week][active[0]]["points"] if active else 0,
            "crew": round(sum(peer_totals) / len(peer_totals), 1) if peer_totals else None,
            "peerPlayers": len(peer_totals),
            "played": per_week[week][me]["played"],
        })
    frequencies = sorted(
        (pid for pid, items in podiums.items() if items),
        key=lambda pid: (-len(podiums[pid]),
                         -sum(x["place"] == 1 for x in podiums[pid]),
                         -sum(x["place"] == 2 for x in podiums[pid]),
                         names.get(pid, "").casefold(), pid),
    )
    podium_count = len(podiums[me])
    podium_rank = frequencies.index(me) + 1 if me in frequencies else None
    if podium_rank is not None and podium_rank <= 3:
        chapters.append(beat(
            "podium", "THE PODIUM", "You kept showing up at the top.",
            podium_count, f"{podium_count} weekly Top 3 finishes across {weeks_total} scheduled weeks.",
            "Each week: totals ranked by points, completed games, then username. "
            "Podium-frequency rank uses number of appearances, first places, then second places.",
            {"weeks": podiums[me], "count": podium_count,
             "frequencyRank": podium_rank, "weeksTotal": weeks_total},
        ))

    # 3. Show own weekly points against the weekly highest and peer average. Peak is
    # the maximum own weekly total, never confused with "won the week".
    best = max(weekly, key=lambda w: (w["mine"], -w["week"])) if weekly else None
    if best and any(w["played"] for w in weekly):
        chapters.append(beat(
            "weekly_trend", "THE SIX-WEEK JOURNEY", "Every week changed the picture.",
            str(weeks_total), "Your weekly totals alongside the weekly highest and other active players' average.",
            "Game-date week; eligible completion points. The highest is the week's highest "
            "player total, not a theoretical maximum. CREW is the mean weekly total of "
            "other player accounts with at least one eligible completion that week; "
            "owner/admin accounts are excluded. Zero-score completions count. "
            "Weeks without peer completions have no benchmark, not a zero average.",
            {"weeks": weekly, "bestWeek": best["week"]},
        ))
        chapters.append(beat(
            "peak_week", "THE HIGH POINT", f"Week {best['week']}. Your moment.",
            best["mine"], f"Your highest-scoring week of Season 01: {best['mine']} points.",
            "Maximum own eligible weekly score; the earlier week wins an exact tie.",
            {"week": best["week"], "score": best["mine"],
             "highest": best["highest"], "wasWeeklyLeader": best["mine"] == best["highest"] and best["mine"] > 0},
        ))

    # 4. Compare *per-player* game averages to give each peer equal weight.
    # A zero attempt is explicitly not comparable.
    comparisons = []
    for key, label in GAMES:
        own = per_game[me][key]
        peers = [sum(games[key]) / len(games[key])
                 for pid, games in per_game.items() if pid != me and games[key]
                 and (peer_ids is None or pid in peer_ids)]
        comparisons.append({
            "key": key, "name": label, "mine": round(sum(own) / len(own), 1) if own else None,
            "crew": round(sum(peers) / len(peers), 1) if peers else None,
            "ownPlayed": len(own), "peerPlayers": len(peers),
        })
    if any(item["ownPlayed"] for item in comparisons):
        chapters.append(beat(
            "game_compare", "YOU VS. THE CREW", "Four games. Your signature.",
            "04", "Average points per completed game, compared with other CREW players.",
            "Own average per completed game. CREW benchmark: mean of other active "
            "player accounts' per-game averages, equally weighted by player. "
            "Owner/admin accounts are excluded from this benchmark.",
            {"games": comparisons},
        ))

    # 5. Points contribution only. The redundant participation chart is intentionally removed.
    breakdown = []
    for key, label in GAMES:
        played = len(per_game[me][key])
        points = sum(per_game[me][key])
        breakdown.append({
            "key": key, "name": label, "played": played, "points": points,
            "gameShare": round(100 * played / all_plays[me], 2) if all_plays[me] else 0,
            "pointShare": round(100 * points / all_points[me], 2) if all_points[me] > 0 else 0,
        })
    if all_points[me] > 0:
        chapters.append(beat(
            "game_dna", "YOUR GAME DNA", "Where your points came from.",
            all_points[me], "Your four games' contributions to your total Season 01 points.",
            "Points share: points in a game / all eligible own points. "
            "No participation comparison is shown.",
            {"games": breakdown, "totalPlayed": all_plays[me],
             "totalPoints": all_points[me]},
        ))

    # 6. Select a genuine surprise not duplicating score, average or peak
    # content. A same-puzzle field comparison must have at least three peers.
    report = recap.get("analyticsStory", {})
    cards = {card["key"]: card for card in report.get("cards", [])}
    surprise = cards.get("same_puzzle") or cards.get("closest_rival")
    if surprise:
        chapters.append(beat(
            "plot_twist", "THE PLOT TWIST", surprise["title"],
            surprise["metric"], surprise["story"], surprise["evidence"],
            {"sourceKey": surprise["key"], "comparison": surprise.get("comparison")},
        ))

    # 6A. Actual season badge awards; championship badges already celebrated
    # above are part of the constellation, not re-celebrated as new wins.
    badges = [BADGES_BY_CODE[c] for c in awarded_codes if c in BADGES_BY_CODE]
    badges.sort(key=lambda b: (-RARITY[b.rarity], b.name, b.code))
    if badges:
        chapters.append(beat(
            "trophy_vault", "THE TROPHY VAULT", "Look what you unlocked.",
            len(badges), f"{len(badges)} earned Season 01 badges, in one collection.",
            "Actual season-specific persisted badge awards; frozen at approved "
            "finalization when available. Already celebrated championship awards appear once in collection.",
            {"badges": [{"code": b.code, "name": b.name, "rarity": b.rarity,
                         "gameKey": b.game_key, "vertical": b.vertical}
                        for b in badges],
             "celebrated": official_codes},
        ))

    # 7. Shareable legacy card fields are all real and fully reconciled.
    signature = None
    eligible = [g for g in comparisons if g["mine"] is not None and g["crew"] is not None]
    if eligible:
        signature = max(eligible, key=lambda g: (g["mine"] - g["crew"], -next(
            i for i, (key, _) in enumerate(GAMES) if key == g["key"])))["name"]
    elif recap.get("signature"):
        signature = recap["signature"]["name"]
    chapters.append(beat(
        "legacy", "YOUR SEASON 01 LEGACY", "This season was yours.",
        all_points[me], "One season. One story. Yours to keep.",
        "Rank, completions, points, frequency and earned badges from the same eligible dataset.",
        {"player": recap["username"], "rank": recap["rank"],
         "points": all_points[me], "completed": all_plays[me],
         "podiumWeeks": podium_count, "signature": signature,
         "badges": [{"code": b.code, "name": b.name, "rarity": b.rarity,
                     "gameKey": b.game_key, "vertical": b.vertical}
                    for b in badges[:3]],
         "champion": "season_champion" in official_codes},
    ))

    # 8. No invented launch dates, new features, prizes or confirmed schedule.
    chapters.append(beat(
        "season_two", "THE STORY CONTINUES", "SEASON 02", "02",
        "New games. New rivalries. A new champion.",
        "Teaser only. No unconfirmed Season 02 date or feature announcement.",
        {},
    ))
    return {
        "version": 3, "preview": not recap["finalized"],
        "player": recap["username"], "beats": chapters, "count": len(chapters),
        "method": "Official cutoff for finalized seasons; staff-only preview otherwise. "
                  "Champion titles appear only after finalization. "
                  "Unranked players receive no invented podium or rank.",
    }

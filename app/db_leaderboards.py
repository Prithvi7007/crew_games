"""Read-side CREW scoring and leaderboard queries.

The public app.db API re-exports these functions for existing callers.
SQL and tie-break behavior is unchanged by this module extraction.
"""
import json
from datetime import timedelta

from app import db as store
from app.schedule import CREW_WEEK_ONE_DATE, crew_today, get_week_start


def get_weekly_points(user_key, reference_day=None):
    profile_id = store._profile_id_from_user_key(user_key)
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    thursday = monday + timedelta(days=3)
    row = store.get_db().execute(
        """
        SELECT COALESCE(SUM(score), 0) AS points, COUNT(*) AS completed
        FROM game_completions
        WHERE profile_id = ? AND game_date BETWEEN ? AND ?
        """,
        (profile_id, monday.isoformat(), thursday.isoformat()),
    ).fetchone()
    return {"points": int(row["points"]), "completed": int(row["completed"])}

def get_weekly_leaderboard(reference_day=None, limit=25):
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    thursday = monday + timedelta(days=3)
    rows = store.get_db().execute(
        """
        SELECT
            p.id, p.username, p.avatar,
            COALESCE(SUM(gc.score), 0) AS points,
            COUNT(gc.id) AS completed
        FROM profiles p
        LEFT JOIN game_completions gc
            ON gc.profile_id = p.id
            AND gc.game_date BETWEEN ? AND ?
        GROUP BY p.id, p.username, p.avatar
        ORDER BY points DESC, completed DESC, LOWER(p.username) ASC
        LIMIT ?
        """,
        (monday.isoformat(), thursday.isoformat(), limit),
    ).fetchall()
    return [
        {
            "profile_id": row["id"], "username": row["username"], "avatar": row["avatar"],
            "points": int(row["points"]), "completed": int(row["completed"]),
        }
        for row in rows
    ]

def get_rankings_between(start_date, end_date, limit=10, competitive_only=False, completed_before=None):
    """Rank saved scores in an inclusive range using the public leaderboard rules."""
    start_date = max(start_date, CREW_WEEK_ONE_DATE)
    competitive_clause = "AND gc.competitive = 1" if competitive_only else ""
    cutoff_clause = "AND gc.completed_at < ?" if completed_before is not None else ""
    params = [start_date.isoformat(), end_date.isoformat()]
    if completed_before is not None:
        params.append(completed_before)
    params.append(int(limit))
    rows = store.get_db().execute(
        f"""
        SELECT
            p.id, p.username, p.avatar,
            SUM(gc.score) AS points,
            COUNT(gc.id) AS completed
        FROM profiles p
        JOIN game_completions gc
          ON gc.profile_id = p.id
         {competitive_clause}
         AND gc.game_date BETWEEN ? AND ?
         {cutoff_clause}
        GROUP BY p.id, p.username, p.avatar
        HAVING SUM(gc.score) > 0
        ORDER BY points DESC, completed DESC, LOWER(p.username) ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [
        {
            "profile_id": int(row["id"]),
            "username": row["username"],
            "avatar": row["avatar"],
            "points": int(row["points"]),
            "completed": int(row["completed"]),
            "rank": index,
        }
        for index, row in enumerate(rows, 1)
    ]


def get_competitive_rankings_between(start_date, end_date, limit=10):
    """Return timely competitive scores for callers needing this filter."""
    return get_rankings_between(start_date, end_date, limit=limit, competitive_only=True)


def get_home_leaderboard(reference_day=None, current_profile_id=None):
    """Return the top three plus the current player's exact weekly rank in one query."""
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    thursday = monday + timedelta(days=3)
    current_profile_id = int(current_profile_id or 0)
    rows = store.get_db().execute(
        """
        WITH scores AS (
            SELECT
                p.id AS profile_id,
                p.username,
                p.avatar,
                COALESCE(SUM(gc.score), 0) AS points,
                COUNT(gc.id) AS completed
            FROM profiles p
            LEFT JOIN game_completions gc
                ON gc.profile_id = p.id
                AND gc.game_date BETWEEN ? AND ?
            GROUP BY p.id, p.username, p.avatar
        ), ranked AS (
            SELECT
                profile_id, username, avatar, points, completed,
                ROW_NUMBER() OVER (
                    ORDER BY points DESC, completed DESC, LOWER(username) ASC
                ) AS rank
            FROM scores
            WHERE points > 0
        )
        SELECT profile_id, username, avatar, points, completed, rank
        FROM ranked
        WHERE rank <= 3 OR profile_id = ?
        ORDER BY rank ASC
        """,
        (monday.isoformat(), thursday.isoformat(), current_profile_id),
    ).fetchall()
    result = []
    for row in rows:
        result.append({
            "profile_id": int(row["profile_id"]),
            "username": row["username"],
            "avatar": row["avatar"],
            "points": int(row["points"]),
            "completed": int(row["completed"]),
            "rank": int(row["rank"]),
            "me": int(row["profile_id"]) == current_profile_id,
        })
    return result


def _period_bounds(period, reference_day=None):
    reference_day = reference_day or crew_today()
    if period == "this_week":
        start = get_week_start(reference_day)
        return start, start + timedelta(days=3), "This week"
    if period == "season":
        season = store.get_season_for_date(reference_day)
        if season:
            return (
                season["start_date"],
                season["end_date"],
                f"Season {season['number']} · {season['name']}",
            )
        start = get_week_start(reference_day)
        return start, start + timedelta(days=3), "This week"
    if period == "last_week":
        start = get_week_start(reference_day) - timedelta(days=7)
        return start, start + timedelta(days=3), "Last week"
    if period == "this_month":
        start = reference_day.replace(day=1)
        return start, reference_day, reference_day.strftime("%B")
    if period == "all_time":
        return None, None, "All time"
    return _period_bounds("this_week", reference_day)


def _date_clause(start, end, prefix="game_date"):
    if not start or not end:
        return f" AND {prefix} >= ?", [CREW_WEEK_ONE_DATE.isoformat()]
    bounded_start = max(start, CREW_WEEK_ONE_DATE)
    return f" AND {prefix} BETWEEN ? AND ?", [bounded_start.isoformat(), end.isoformat()]


def get_leaderboard(period="this_week", game_key="all", reference_day=None, current_profile_id=None):
    """Return competitive standings using indexed SQL aggregation for the scoring path."""
    if game_key not in {"all", "mystery", "trivia", "word", "tick_tock"}:
        game_key = "all"
    start, end, period_label = _period_bounds(period, reference_day)
    db = store.get_db()

    join_conditions = ["gc.profile_id = p.id", "gc.game_date >= ?"]
    params = [CREW_WEEK_ONE_DATE.isoformat()]
    if game_key != "all":
        join_conditions.append("gc.game_key = ?")
        params.append(game_key)
    if start and end:
        join_conditions.append("gc.game_date BETWEEN ? AND ?")
        params.extend((start.isoformat(), end.isoformat()))

    profiles = db.execute(
        f"""
        SELECT p.id, p.username, p.avatar,
               COALESCE(SUM(gc.score), 0) AS points,
               COUNT(gc.id) AS completed,
               COALESCE(us.current_streak, 0) AS current_streak
        FROM profiles p
        LEFT JOIN user_stats us ON us.profile_id = p.id
        LEFT JOIN game_completions gc ON {' AND '.join(join_conditions)}
        GROUP BY p.id, p.username, p.avatar, us.current_streak
        ORDER BY LOWER(p.username)
        """,
        params,
    ).fetchall()
    players = {
        int(row["id"]): {
            "profile_id": int(row["id"]),
            "username": row["username"],
            "avatar": row["avatar"],
            "points": int(row["points"]),
            "completed": int(row["completed"]),
            "streak": int(row["current_streak"] or 0),
            "detail": "",
            "secondary": None,
        }
        for row in profiles
    }

    if game_key == "mystery":
        sql = """SELECT a.profile_id, a.revealed_count, a.won, a.game_date
                 FROM mystery_attempts a
                 JOIN game_completions gc ON gc.profile_id = a.profile_id AND gc.game_date = a.game_date
                   AND gc.game_key = 'mystery'
                 WHERE a.completed = 1"""
        clause, metric_params = _date_clause(start, end, prefix="a.game_date")
        for row in db.execute(sql + clause, metric_params).fetchall():
            player = players.get(int(row["profile_id"]))
            if not player:
                continue
            player.setdefault("clues_total", 0)
            player.setdefault("solved", 0)
            player.setdefault("metric_count", 0)
            player["clues_total"] += int(row["revealed_count"])
            player["metric_count"] += 1
            player["solved"] += int(row["won"])
        for player in players.values():
            if player.get("metric_count"):
                avg = player["clues_total"] / player["metric_count"]
                player["secondary"] = avg
                player["detail"] = f"{player['solved']} solved · {avg:.1f} avg clues"

    elif game_key == "trivia":
        sql = """SELECT a.profile_id, a.answers_json, a.game_date
                 FROM trivia_attempts a
                 JOIN game_completions gc ON gc.profile_id = a.profile_id AND gc.game_date = a.game_date
                   AND gc.game_key = 'trivia'
                 WHERE a.completed = 1"""
        clause, metric_params = _date_clause(start, end, prefix="a.game_date")
        for row in db.execute(sql + clause, metric_params).fetchall():
            player = players.get(int(row["profile_id"]))
            if not player:
                continue
            try:
                answers = json.loads(row["answers_json"] or "[]")
            except json.JSONDecodeError:
                answers = []
            player.setdefault("correct", 0)
            player.setdefault("questions", 0)
            player["correct"] += sum(1 for answer in answers if answer.get("correct"))
            player["questions"] += len(answers)
        for player in players.values():
            if player.get("questions"):
                accuracy = (player["correct"] / player["questions"]) * 100
                player["secondary"] = -accuracy
                player["detail"] = f"{accuracy:.0f}% · {player['correct']}/{player['questions']} correct"

    elif game_key == "word":
        sql = """SELECT a.profile_id, a.guesses_json, a.won, a.game_date
                 FROM word_attempts a
                 JOIN game_completions gc ON gc.profile_id = a.profile_id AND gc.game_date = a.game_date
                   AND gc.game_key = 'word'
                 WHERE a.completed = 1"""
        clause, metric_params = _date_clause(start, end, prefix="a.game_date")
        for row in db.execute(sql + clause, metric_params).fetchall():
            player = players.get(int(row["profile_id"]))
            if not player:
                continue
            try:
                guesses = json.loads(row["guesses_json"] or "[]")
            except json.JSONDecodeError:
                guesses = []
            player.setdefault("guess_total", 0)
            player.setdefault("wins", 0)
            player.setdefault("word_count", 0)
            player["guess_total"] += len(guesses)
            player["wins"] += int(row["won"])
            player["word_count"] += 1
        for player in players.values():
            if player.get("word_count"):
                avg = player["guess_total"] / player["word_count"]
                winrate = (player["wins"] / player["word_count"]) * 100
                player["secondary"] = avg
                player["detail"] = f"{winrate:.0f}% win · {avg:.1f} avg guesses"

    elif game_key == "tick_tock":
        sql = """SELECT a.profile_id, a.target_seconds, a.elapsed_seconds, a.difference_seconds, a.game_date
                 FROM tick_tock_attempts a
                 JOIN game_completions gc ON gc.profile_id = a.profile_id AND gc.game_date = a.game_date
                   AND gc.game_key = 'tick_tock'
                 WHERE a.completed = 1"""
        clause, metric_params = _date_clause(start, end, prefix="a.game_date")
        for row in db.execute(sql + clause, metric_params).fetchall():
            player = players.get(int(row["profile_id"]))
            if not player:
                continue
            diff = float(row["difference_seconds"] or 0)
            signed = float(row["elapsed_seconds"] or 0) - float(row["target_seconds"] or 0)
            player.setdefault("diff_total", 0.0)
            player.setdefault("timer_count", 0)
            player.setdefault("best_abs", None)
            player.setdefault("best_signed", 0.0)
            player["diff_total"] += diff
            player["timer_count"] += 1
            if player["best_abs"] is None or diff < player["best_abs"]:
                player["best_abs"] = diff
                player["best_signed"] = signed
        for player in players.values():
            if player.get("timer_count"):
                avg = player["diff_total"] / player["timer_count"]
                player["secondary"] = avg
                sign = "+" if player["best_signed"] >= 0 else "−"
                player["detail"] = f"{avg:.2f}s avg off · best {sign}{abs(player['best_signed']):.2f}s"
    else:
        for player in players.values():
            if player["completed"]:
                player["detail"] = f"{player['completed']} game{'s' if player['completed'] != 1 else ''} complete"

    ranked = [player for player in players.values() if player["points"] > 0]
    if game_key in {"mystery", "word", "tick_tock"}:
        ranked.sort(key=lambda player: (-player["points"], player["secondary"] if player["secondary"] is not None else 999999, player["username"].lower()))
    elif game_key == "trivia":
        ranked.sort(key=lambda player: (-player["points"], player["secondary"] if player["secondary"] is not None else 0, player["username"].lower()))
    else:
        ranked.sort(key=lambda player: (-player["points"], -player["completed"], player["username"].lower()))

    for index, player in enumerate(ranked, 1):
        player["rank"] = index
        player["me"] = player["profile_id"] == current_profile_id
        for key in ("clues_total", "solved", "metric_count", "correct", "questions", "guess_total", "wins", "word_count", "diff_total", "timer_count", "best_abs", "best_signed", "secondary"):
            player.pop(key, None)

    me = next((player for player in ranked if player["me"]), None)
    if me is None and current_profile_id is not None:
        candidate = players.get(int(current_profile_id))
        if candidate:
            me = {
                "profile_id": candidate["profile_id"],
                "username": candidate["username"],
                "avatar": candidate["avatar"],
                "points": 0,
                "completed": 0,
                "streak": int(candidate.get("streak", 0)),
                "detail": "No score in this view yet",
                "rank": None,
                "me": True,
            }
    return {
        "period": period,
        "period_label": period_label,
        "game": game_key,
        "players": ranked,
        "me": me,
        "top": ranked[:3],
        "total_ranked": len(ranked),
    }



def get_championship_score_rows(start_date, end_date, *, completed_before=None):
    """Season totals for awards; an optional UTC cutoff freezes eligibility.

    The normal public leaderboards deliberately have no approval cutoff:
    archived games still earn personal and season points after awards close.
    """
    params = [start_date.isoformat(), end_date.isoformat()]
    cutoff_clause = ""
    if completed_before is not None:
        cutoff_clause = " AND gc.completed_at < ?"
        params.append(completed_before)
    return store.get_db().execute(
        f"""
        SELECT p.id AS profile_id, p.username, gc.game_key,
               SUM(gc.score) AS points
        FROM game_completions gc
        JOIN profiles p ON p.id = gc.profile_id
        WHERE gc.game_date BETWEEN ? AND ?
          AND gc.game_key IN ('mystery','trivia','word','tick_tock')
          {cutoff_clause}
        GROUP BY p.id, p.username, gc.game_key
        """,
        params,
    ).fetchall()

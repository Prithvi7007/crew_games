import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import click
from flask import current_app, g
from sqlalchemy import create_engine, event, inspect, text

from app.migrations import current_revision, upgrade_database
from app.schedule import crew_today, get_week_start, previous_scheduled_game_day


class _Result:
    def __init__(self, result):
        self._result = result

    def fetchone(self):
        return self._result.mappings().fetchone()

    def fetchall(self):
        return self._result.mappings().fetchall()

    @property
    def rowcount(self):
        return self._result.rowcount


class _Connection:
    def __init__(self, connection):
        self._connection = connection

    @staticmethod
    def _bind(sql, params):
        params = tuple(params or ())
        if not params:
            return sql, {}
        chunks = sql.split("?")
        if len(chunks) - 1 != len(params):
            raise ValueError("SQL placeholder count does not match parameter count")
        pieces = [chunks[0]]
        values = {}
        for index, value in enumerate(params):
            name = f"p{index}"
            pieces.extend((f":{name}", chunks[index + 1]))
            values[name] = value
        return "".join(pieces), values

    def execute(self, sql, params=()):
        statement, values = self._bind(sql, params)
        return _Result(self._connection.execute(text(statement), values))

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def _engine():
    return current_app.extensions["crew_db_engine"]


def get_db():
    if "db" not in g:
        g.db = _Connection(_engine().connect())
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def utc_now():
    return datetime.now(timezone.utc)


def _db_timestamp(value=None):
    """Canonical UTC timestamp text, generated from timezone-aware datetime objects."""
    value = (value or utc_now()).astimezone(timezone.utc)
    # Keep the v11 wire/storage format during the v12 expand phase so code rollback
    # remains safe. A future contract migration can move storage to TIMESTAMPTZ.
    return value.replace(tzinfo=None).isoformat(timespec="seconds")


def _profile_id_from_user_key(user_key):
    value = str(user_key or "")
    if not value.startswith("profile:"):
        raise ValueError("CREW data is not linked to a profile")
    try:
        profile_id = int(value.split(":", 1)[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("CREW profile key is invalid") from exc
    if profile_id < 1:
        raise ValueError("CREW profile key is invalid")
    return profile_id


def _calculate_streaks(completion_days):
    days = sorted(set(completion_days))
    if not days:
        return 0, 0, None
    running = 0
    longest = 0
    previous = None
    for completed_day in days:
        if previous and previous_scheduled_game_day(completed_day) == previous:
            running += 1
        else:
            running = 1
        longest = max(longest, running)
        previous = completed_day
    day_set = set(days)
    current = 1
    cursor = days[-1]
    while True:
        prior = previous_scheduled_game_day(cursor)
        if prior not in day_set:
            break
        current += 1
        cursor = prior
    return current, longest, days[-1].isoformat()


def ping_db():
    row = get_db().execute("SELECT 1 AS ok").fetchone()
    return bool(row and row["ok"] == 1)


def _integrity_issues():
    db = get_db()
    tables = set(inspect(_engine()).get_table_names())
    profile_ids = {int(row["id"]) for row in db.execute("SELECT id FROM profiles").fetchall()} if "profiles" in tables else set()
    issues = []
    for table in ("word_attempts", "mystery_attempts", "trivia_attempts", "tick_tock_attempts", "game_completions", "user_stats"):
        if table not in tables:
            continue
        bad = 0
        for row in db.execute(f"SELECT user_key FROM {table}").fetchall():
            try:
                profile_id = _profile_id_from_user_key(row["user_key"])
            except ValueError:
                bad += 1
                continue
            if profile_id not in profile_ids:
                bad += 1
        if bad:
            issues.append(f"{table}: {bad} row(s) are not linked to an existing profile")
    return issues


def init_app(app):
    if app.config["DATABASE_URL"].startswith("sqlite:///"):
        os.makedirs(app.instance_path, exist_ok=True)
        engine = create_engine(
            app.config["DATABASE_URL"],
            future=True,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    else:
        engine = create_engine(
            app.config["DATABASE_URL"],
            future=True,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=app.config.get("DB_POOL_SIZE", 5),
            max_overflow=app.config.get("DB_MAX_OVERFLOW", 5),
            pool_timeout=app.config.get("DB_POOL_TIMEOUT", 10),
        )
    app.extensions["crew_db_engine"] = engine
    app.teardown_appcontext(close_db)

    @app.cli.command("db-upgrade")
    def db_upgrade_command():
        """Upgrade the CREW database to the latest Alembic revision."""
        issues = _integrity_issues() if inspect(engine).has_table("profiles") else []
        if issues:
            raise click.ClickException("Database integrity preflight failed: " + "; ".join(issues))
        upgrade_database(app.config["DATABASE_URL"])
        click.echo(f"CREW database upgraded to {current_revision(app.config['DATABASE_URL'])}.")

    @app.cli.command("db-revision")
    def db_revision_command():
        """Print the active Alembic revision."""
        click.echo(current_revision(app.config["DATABASE_URL"]) or "unversioned")

    @app.cli.command("db-integrity-check")
    def db_integrity_check_command():
        """Validate legacy profile links before a platform migration."""
        issues = _integrity_issues()
        if issues:
            raise click.ClickException("; ".join(issues))
        click.echo("CREW database integrity preflight passed.")

    @app.cli.command("security-cleanup")
    @click.option("--event-days", default=90, type=click.IntRange(7, 3650), show_default=True)
    def security_cleanup_command(event_days):
        """Purge expired rate-limit buckets and old pseudonymous security audit events."""
        purge_security_state(event_age_days=event_days)
        click.echo("CREW security state cleaned.")

    if app.config.get("AUTO_DB_MIGRATE"):
        upgrade_database(app.config["DATABASE_URL"])


def ensure_user_stats(user_key):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM user_stats WHERE profile_id = ?", (profile_id,)
    ).fetchone()
    if row:
        return row

    db.execute(
        """
        INSERT INTO user_stats (
            user_key, profile_id, current_streak, longest_streak, total_word_points,
            word_games_completed, word_games_won, last_completed_date,
            total_points, games_completed
        ) VALUES (?, ?, 0, 0, 0, 0, 0, NULL, 0, 0)
        ON CONFLICT (profile_id) DO NOTHING
        """,
        (user_key, profile_id),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM user_stats WHERE profile_id = ?", (profile_id,)
    ).fetchone()


# ---------- Anonymous CREW profiles ----------

def create_profile(username, password_hash, avatar, recovery_code_hash):
    db = get_db()
    created_at = _db_timestamp()
    db.execute(
        """
        INSERT INTO profiles (username, password_hash, avatar, recovery_code_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, password_hash, avatar, recovery_code_hash, created_at),
    )
    db.commit()
    return get_profile_by_username(username)


def get_profile_by_id(profile_id):
    return get_db().execute(
        "SELECT * FROM profiles WHERE id = ?", (profile_id,)
    ).fetchone()


def get_profile_by_username(username):
    return get_db().execute(
        "SELECT * FROM profiles WHERE LOWER(username) = LOWER(?)", (username,)
    ).fetchone()


def touch_profile_login(profile_id):
    db = get_db()
    db.execute(
        "UPDATE profiles SET last_login_at = ? WHERE id = ?",
        (_db_timestamp(), profile_id),
    )
    db.commit()


def update_profile_credentials(profile_id, password_hash, recovery_code_hash):
    db = get_db()
    db.execute(
        """
        UPDATE profiles
        SET password_hash = ?, recovery_code_hash = ?, session_version = session_version + 1
        WHERE id = ?
        """,
        (password_hash, recovery_code_hash, profile_id),
    )
    db.commit()
    return get_profile_by_id(profile_id)


def update_profile_avatar(profile_id, avatar):
    db = get_db()
    db.execute("UPDATE profiles SET avatar = ? WHERE id = ?", (avatar, profile_id))
    db.commit()
    return get_profile_by_id(profile_id)


def update_profile_password(profile_id, password_hash):
    db = get_db()
    db.execute(
        "UPDATE profiles SET password_hash = ?, session_version = session_version + 1 WHERE id = ?",
        (password_hash, profile_id),
    )
    db.commit()
    return get_profile_by_id(profile_id)


def update_profile_recovery_code(profile_id, recovery_code_hash):
    db = get_db()
    db.execute("UPDATE profiles SET recovery_code_hash = ? WHERE id = ?", (recovery_code_hash, profile_id))
    db.commit()


def profile_user_key(profile_id):
    return f"profile:{int(profile_id)}"


# ---------- Security state ----------

def get_rate_limit(limiter_key, window_seconds, now=None):
    now = int(now or time.time())
    row = get_db().execute(
        "SELECT window_started_at, attempts FROM security_rate_limits WHERE limiter_key = ?",
        (limiter_key,),
    ).fetchone()
    if not row or now - int(row["window_started_at"]) >= int(window_seconds):
        return {"attempts": 0, "limited": False, "retry_after": 0}
    attempts = int(row["attempts"])
    retry_after = max(1, int(window_seconds) - (now - int(row["window_started_at"])))
    return {"attempts": attempts, "limited": False, "retry_after": retry_after}


def record_rate_limit_failure(limiter_key, window_seconds, now=None):
    now = int(now or time.time())
    cutoff = now - int(window_seconds)
    db = get_db()
    # SQLite and PostgreSQL both support this UPSERT form. Keeping the increment
    # in one statement avoids a cross-worker select/insert race in Gunicorn.
    db.execute(
        """
        INSERT INTO security_rate_limits (limiter_key, window_started_at, attempts)
        VALUES (?, ?, 1)
        ON CONFLICT (limiter_key) DO UPDATE SET
            attempts = CASE
                WHEN security_rate_limits.window_started_at <= ? THEN 1
                ELSE security_rate_limits.attempts + 1
            END,
            window_started_at = CASE
                WHEN security_rate_limits.window_started_at <= ? THEN ?
                ELSE security_rate_limits.window_started_at
            END
        """,
        (limiter_key, now, cutoff, cutoff, now),
    )
    db.commit()
    row = db.execute(
        "SELECT attempts FROM security_rate_limits WHERE limiter_key = ?",
        (limiter_key,),
    ).fetchone()
    return int(row["attempts"]) if row else 0


def clear_rate_limit(limiter_key):
    db = get_db()
    db.execute("DELETE FROM security_rate_limits WHERE limiter_key = ?", (limiter_key,))
    db.commit()


def log_security_event(event_type, subject_hash="", ip_hash="", metadata=None):
    db = get_db()
    db.execute(
        "INSERT INTO security_events (event_type, subject_hash, ip_hash, occurred_at, metadata_json) VALUES (?, ?, ?, ?, ?)",
        (
            str(event_type)[:80],
            str(subject_hash)[:128],
            str(ip_hash)[:128],
            _db_timestamp(),
            json.dumps(metadata or {}, separators=(",", ":")),
        ),
    )
    db.commit()


def purge_security_state(rate_limit_age_seconds=86400, event_age_days=90):
    db = get_db()
    now = int(time.time())
    cutoff = _db_timestamp(utc_now() - timedelta(days=event_age_days))
    db.execute("DELETE FROM security_rate_limits WHERE window_started_at < ?", (now - rate_limit_age_seconds,))
    db.execute("DELETE FROM security_events WHERE occurred_at < ?", (cutoff,))
    db.commit()


def load_json_list(row, column):
    try:
        value = json.loads(row[column] or "[]")
    except (TypeError, json.JSONDecodeError):
        value = []
    return value if isinstance(value, list) else []


# ---------- Word ----------

def get_or_create_word_attempt(user_key, game_date):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM word_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO word_attempts (user_key, profile_id, game_date) VALUES (?, ?, ?) ON CONFLICT (profile_id, game_date) DO NOTHING",
        (user_key, profile_id, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM word_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()

def load_guesses(attempt_row):
    return load_json_list(attempt_row, "guesses_json")


def save_word_attempt(user_key, game_date, guesses, completed, won, score):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    completed_at = _db_timestamp() if completed else None
    db.execute(
        """
        UPDATE word_attempts
        SET guesses_json = ?, completed = ?, won = ?, score = ?, completed_at = ?
        WHERE profile_id = ? AND game_date = ?
        """,
        (json.dumps(guesses), int(completed), int(won), score, completed_at, profile_id, game_date),
    )
    db.commit()

# ---------- Mystery ----------

def get_or_create_mystery_attempt(user_key, game_date):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM mystery_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO mystery_attempts (user_key, profile_id, game_date) VALUES (?, ?, ?) ON CONFLICT (profile_id, game_date) DO NOTHING",
        (user_key, profile_id, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM mystery_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()

def save_mystery_attempt(user_key, game_date, revealed_count, guesses, completed, won, score):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    completed_at = _db_timestamp() if completed else None
    db.execute(
        """
        UPDATE mystery_attempts
        SET revealed_count = ?, guesses_json = ?, completed = ?, won = ?, score = ?, completed_at = ?
        WHERE profile_id = ? AND game_date = ?
        """,
        (revealed_count, json.dumps(guesses), int(completed), int(won), score, completed_at, profile_id, game_date),
    )
    db.commit()

# ---------- Trivia ----------

def get_or_create_trivia_attempt(user_key, game_date):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM trivia_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO trivia_attempts (user_key, profile_id, game_date) VALUES (?, ?, ?) ON CONFLICT (profile_id, game_date) DO NOTHING",
        (user_key, profile_id, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM trivia_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()

def save_trivia_attempt(user_key, game_date, answers, completed, score):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    completed_at = _db_timestamp() if completed else None
    db.execute(
        """
        UPDATE trivia_attempts
        SET answers_json = ?, completed = ?, score = ?, completed_at = ?
        WHERE profile_id = ? AND game_date = ?
        """,
        (json.dumps(answers), int(completed), score, completed_at, profile_id, game_date),
    )
    db.commit()

# ---------- Tick-Tock ----------

def get_or_create_tick_tock_attempt(user_key, game_date, target_seconds):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM tick_tock_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        """
        INSERT INTO tick_tock_attempts (user_key, profile_id, game_date, target_seconds)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (profile_id, game_date) DO NOTHING
        """,
        (user_key, profile_id, game_date, target_seconds),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM tick_tock_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()

def start_tick_tock_attempt(user_key, game_date):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    started_at = time.time()
    db.execute(
        """
        UPDATE tick_tock_attempts
        SET started_at = ?, stopped_at = NULL, elapsed_seconds = NULL, difference_seconds = NULL
        WHERE profile_id = ? AND game_date = ? AND completed = 0
        """,
        (started_at, profile_id, game_date),
    )
    db.commit()
    return started_at

def finish_tick_tock_attempt(user_key, game_date, elapsed_seconds, difference_seconds, score):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    stopped_at = time.time()
    completed_at = _db_timestamp()
    db.execute(
        """
        UPDATE tick_tock_attempts
        SET stopped_at = ?, elapsed_seconds = ?, difference_seconds = ?,
            completed = 1, score = ?, completed_at = ?
        WHERE profile_id = ? AND game_date = ?
        """,
        (stopped_at, elapsed_seconds, difference_seconds, score, completed_at, profile_id, game_date),
    )
    db.commit()

# ---------- Shared progress / scoring ----------

def finalize_game_stats(user_key, game_key, game_date, score, won=True, competitive=True):
    """Record a game completion once. Archive completions never alter competitive totals/streaks."""
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    stats = ensure_user_stats(user_key)
    completed_at = _db_timestamp()
    cursor = db.execute(
        """
        INSERT INTO game_completions (
            user_key, profile_id, game_key, game_date, score, won, completed_at, competitive
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (profile_id, game_key, game_date) DO NOTHING
        """,
        (user_key, profile_id, game_key, game_date, score, int(won), completed_at, int(bool(competitive))),
    )

    if cursor.rowcount == 0:
        return ensure_user_stats(user_key)

    if not competitive:
        db.commit()
        return ensure_user_stats(user_key)

    completion_rows = db.execute(
        "SELECT DISTINCT game_date FROM game_completions WHERE profile_id = ? AND competitive = 1 ORDER BY game_date ASC",
        (profile_id,),
    ).fetchall()
    completion_days = []
    for item in completion_rows:
        try:
            completion_days.append(date.fromisoformat(item["game_date"]))
        except (TypeError, ValueError):
            continue
    current_streak, calculated_longest, last_completed_date = _calculate_streaks(completion_days)
    longest_streak = max(int(stats["longest_streak"]), calculated_longest)

    word_points = score if game_key == "word" else 0
    word_completed = 1 if game_key == "word" else 0
    word_won = 1 if game_key == "word" and won else 0

    db.execute(
        """
        UPDATE user_stats
        SET current_streak = ?,
            longest_streak = ?,
            total_points = total_points + ?,
            games_completed = games_completed + 1,
            total_word_points = total_word_points + ?,
            word_games_completed = word_games_completed + ?,
            word_games_won = word_games_won + ?,
            last_completed_date = ?
        WHERE profile_id = ?
        """,
        (current_streak, longest_streak, score, word_points, word_completed, word_won, last_completed_date, profile_id),
    )
    db.commit()
    return ensure_user_stats(user_key)

def finalize_word_stats(user_key, game_date, won, score, competitive=True):
    return finalize_game_stats(user_key, "word", game_date, score, won, competitive=competitive)


def get_game_completion(user_key, game_key, game_date):
    profile_id = _profile_id_from_user_key(user_key)
    return get_db().execute(
        "SELECT * FROM game_completions WHERE profile_id = ? AND game_key = ? AND game_date = ?",
        (profile_id, game_key, game_date),
    ).fetchone()

def get_weekly_points(user_key, reference_day=None):
    profile_id = _profile_id_from_user_key(user_key)
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    thursday = monday + timedelta(days=3)
    row = get_db().execute(
        """
        SELECT COALESCE(SUM(score), 0) AS points, COUNT(*) AS completed
        FROM game_completions
        WHERE profile_id = ? AND competitive = 1 AND game_date BETWEEN ? AND ?
        """,
        (profile_id, monday.isoformat(), thursday.isoformat()),
    ).fetchone()
    return {"points": int(row["points"]), "completed": int(row["completed"])}

def get_weekly_leaderboard(reference_day=None, limit=25):
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    thursday = monday + timedelta(days=3)
    rows = get_db().execute(
        """
        SELECT
            p.id, p.username, p.avatar,
            COALESCE(SUM(gc.score), 0) AS points,
            COUNT(gc.id) AS completed
        FROM profiles p
        LEFT JOIN game_completions gc
            ON gc.profile_id = p.id
            AND gc.competitive = 1
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

def get_home_leaderboard(reference_day=None, current_profile_id=None):
    """Return the top three plus the current player's exact weekly rank in one query."""
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    thursday = monday + timedelta(days=3)
    current_profile_id = int(current_profile_id or 0)
    rows = get_db().execute(
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
                AND gc.competitive = 1
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
        return "", []
    return f" AND {prefix} BETWEEN ? AND ?", [start.isoformat(), end.isoformat()]


def get_leaderboard(period="this_week", game_key="all", reference_day=None, current_profile_id=None):
    """Return competitive standings using indexed SQL aggregation for the scoring path."""
    if game_key not in {"all", "mystery", "trivia", "word", "tick_tock"}:
        game_key = "all"
    start, end, period_label = _period_bounds(period, reference_day)
    db = get_db()

    join_conditions = ["gc.profile_id = p.id", "gc.competitive = 1"]
    params = []
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
               COUNT(gc.id) AS completed
        FROM profiles p
        LEFT JOIN game_completions gc ON {' AND '.join(join_conditions)}
        GROUP BY p.id, p.username, p.avatar
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
            "detail": "",
            "secondary": None,
        }
        for row in profiles
    }

    if game_key == "mystery":
        sql = """SELECT a.profile_id, a.revealed_count, a.won, a.game_date
                 FROM mystery_attempts a
                 JOIN game_completions gc ON gc.profile_id = a.profile_id AND gc.game_date = a.game_date
                   AND gc.game_key = 'mystery' AND gc.competitive = 1
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
                   AND gc.game_key = 'trivia' AND gc.competitive = 1
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
                   AND gc.game_key = 'word' AND gc.competitive = 1
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
                   AND gc.game_key = 'tick_tock' AND gc.competitive = 1
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

def get_profile_history_summary(user_key):
    profile_id = _profile_id_from_user_key(user_key)
    row = get_db().execute(
        """SELECT COUNT(*) AS completed,
                  COALESCE(SUM(CASE WHEN competitive = 1 THEN 1 ELSE 0 END), 0) AS live_completed,
                  COALESCE(SUM(CASE WHEN competitive = 0 THEN 1 ELSE 0 END), 0) AS archive_completed
           FROM game_completions WHERE profile_id = ?""",
        (profile_id,),
    ).fetchone()
    return {
        "completed": int(row["completed"]),
        "live_completed": int(row["live_completed"]),
        "archive_completed": int(row["archive_completed"]),
    }

def get_game_attempt_summary(user_key, game_key, game_date):
    db = get_db()
    profile_id = _profile_id_from_user_key(user_key)
    table_by_key = {
        "mystery": "mystery_attempts",
        "trivia": "trivia_attempts",
        "word": "word_attempts",
        "tick_tock": "tick_tock_attempts",
    }
    table = table_by_key[game_key]
    row = db.execute(
        f"SELECT * FROM {table} WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if not row:
        return {"started": False, "completed": False, "score": 0}

    started = True
    if game_key == "tick_tock":
        started = bool(row["started_at"])
    elif game_key == "trivia":
        started = bool(load_json_list(row, "answers_json"))
    elif game_key in ("word", "mystery"):
        started = bool(load_json_list(row, "guesses_json")) or (game_key == "mystery" and row["revealed_count"] > 1)

    return {"started": started, "completed": bool(row["completed"]), "score": int(row["score"])}

# ---------- Admin-managed game content ----------

CONTENT_GAME_KEYS = {"mystery", "trivia", "word", "tick_tock"}


def get_game_content(game_key, game_date, published_only=False):
    if game_key not in CONTENT_GAME_KEYS:
        raise ValueError("Unknown game key")
    row = get_db().execute(
        "SELECT * FROM game_content WHERE game_key = ? AND game_date = ?",
        (game_key, game_date),
    ).fetchone()
    if not row or (published_only and row["status"] != "published"):
        return None
    try:
        content = json.loads(row["content_json"] or "{}")
    except json.JSONDecodeError:
        content = {}
    return {
        "id": row["id"],
        "game_key": row["game_key"],
        "game_date": row["game_date"],
        "status": row["status"],
        "theme_label": row["theme_label"] or "",
        "content": content if isinstance(content, dict) else {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "published_at": row["published_at"],
    }


def save_game_content(game_key, game_date, theme_label, content, status="draft"):
    if game_key not in CONTENT_GAME_KEYS:
        raise ValueError("Unknown game key")
    if status not in {"draft", "published"}:
        raise ValueError("Invalid content status")
    db = get_db()
    now = _db_timestamp()
    existing = db.execute(
        "SELECT id, created_at FROM game_content WHERE game_key = ? AND game_date = ?",
        (game_key, game_date),
    ).fetchone()
    payload = json.dumps(content, ensure_ascii=False)
    published_at = now if status == "published" else None
    if existing:
        db.execute(
            """
            UPDATE game_content
            SET theme_label = ?, content_json = ?, status = ?, updated_at = ?,
                published_at = CASE WHEN ? = 'published' THEN COALESCE(published_at, ?) ELSE NULL END
            WHERE game_key = ? AND game_date = ?
            """,
            (theme_label.strip(), payload, status, now, status, published_at, game_key, game_date),
        )
    else:
        db.execute(
            """
            INSERT INTO game_content (
                game_key, game_date, status, theme_label, content_json,
                created_at, updated_at, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (game_key, game_date, status, theme_label.strip(), payload, now, now, published_at),
        )
    db.commit()
    return get_game_content(game_key, game_date)


def set_game_content_status(game_key, game_date, status):
    if status not in {"draft", "published"}:
        raise ValueError("Invalid content status")
    row = get_game_content(game_key, game_date)
    if not row:
        return None
    return save_game_content(
        game_key,
        game_date,
        row["theme_label"],
        row["content"],
        status=status,
    )


def get_week_content(reference_day=None):
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    items = []
    for offset, game_key in enumerate(("mystery", "trivia", "word", "tick_tock")):
        game_day = monday.fromordinal(monday.toordinal() + offset)
        row = get_game_content(game_key, game_day.isoformat())
        items.append({"game_key": game_key, "game_date": game_day.isoformat(), "row": row})
    return items


def count_game_attempts(game_key, game_date):
    # Opening a preview may create an empty attempt row. Content only locks when
    # a player has actually interacted with the game.
    started_clause = {
        "mystery": "(guesses_json <> '[]' OR revealed_count > 1 OR completed = 1)",
        "trivia": "(answers_json <> '[]' OR completed = 1)",
        "word": "(guesses_json <> '[]' OR completed = 1)",
        "tick_tock": "(started_at IS NOT NULL OR completed = 1)",
    }[game_key]
    table = {
        "mystery": "mystery_attempts",
        "trivia": "trivia_attempts",
        "word": "word_attempts",
        "tick_tock": "tick_tock_attempts",
    }[game_key]
    row = get_db().execute(
        f"SELECT COUNT(*) AS count FROM {table} WHERE game_date = ? AND {started_clause}",
        (game_date,),
    ).fetchone()
    return int(row["count"])

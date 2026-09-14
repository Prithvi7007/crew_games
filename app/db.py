import json
import os
import time
from datetime import date, datetime, timedelta

import click
from flask import current_app, g
from sqlalchemy import create_engine, inspect, text

from app.schedule import crew_today, get_week_start, previous_scheduled_game_day


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    avatar TEXT NOT NULL,
    recovery_code_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS word_games (
    game_date TEXT PRIMARY KEY,
    solution TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS word_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    guesses_json TEXT NOT NULL DEFAULT '[]',
    completed INTEGER NOT NULL DEFAULT 0,
    won INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(user_key, game_date)
);
CREATE TABLE IF NOT EXISTS mystery_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    revealed_count INTEGER NOT NULL DEFAULT 1,
    guesses_json TEXT NOT NULL DEFAULT '[]',
    completed INTEGER NOT NULL DEFAULT 0,
    won INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(user_key, game_date)
);
CREATE TABLE IF NOT EXISTS trivia_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    answers_json TEXT NOT NULL DEFAULT '[]',
    completed INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(user_key, game_date)
);
CREATE TABLE IF NOT EXISTS tick_tock_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    target_seconds REAL NOT NULL,
    started_at REAL,
    stopped_at REAL,
    elapsed_seconds REAL,
    difference_seconds REAL,
    completed INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(user_key, game_date)
);
CREATE TABLE IF NOT EXISTS game_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT NOT NULL,
    game_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    won INTEGER NOT NULL DEFAULT 1,
    completed_at TEXT NOT NULL,
    competitive INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_key, game_key, game_date)
);
CREATE TABLE IF NOT EXISTS user_stats (
    user_key TEXT PRIMARY KEY,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    total_word_points INTEGER NOT NULL DEFAULT 0,
    word_games_completed INTEGER NOT NULL DEFAULT 0,
    word_games_won INTEGER NOT NULL DEFAULT 0,
    last_completed_date TEXT,
    total_points INTEGER NOT NULL DEFAULT 0,
    games_completed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    theme_label TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    published_at TEXT,
    UNIQUE(game_key, game_date)
);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    avatar TEXT NOT NULL,
    recovery_code_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_username_lower ON profiles (LOWER(username));
CREATE TABLE IF NOT EXISTS word_games (
    game_date TEXT PRIMARY KEY,
    solution TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS word_attempts (
    id BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    guesses_json TEXT NOT NULL DEFAULT '[]',
    completed INTEGER NOT NULL DEFAULT 0,
    won INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(user_key, game_date)
);
CREATE TABLE IF NOT EXISTS mystery_attempts (
    id BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    revealed_count INTEGER NOT NULL DEFAULT 1,
    guesses_json TEXT NOT NULL DEFAULT '[]',
    completed INTEGER NOT NULL DEFAULT 0,
    won INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(user_key, game_date)
);
CREATE TABLE IF NOT EXISTS trivia_attempts (
    id BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    answers_json TEXT NOT NULL DEFAULT '[]',
    completed INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(user_key, game_date)
);
CREATE TABLE IF NOT EXISTS tick_tock_attempts (
    id BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    target_seconds DOUBLE PRECISION NOT NULL,
    started_at DOUBLE PRECISION,
    stopped_at DOUBLE PRECISION,
    elapsed_seconds DOUBLE PRECISION,
    difference_seconds DOUBLE PRECISION,
    completed INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(user_key, game_date)
);
CREATE TABLE IF NOT EXISTS game_completions (
    id BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    game_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    won INTEGER NOT NULL DEFAULT 1,
    completed_at TEXT NOT NULL,
    competitive INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_key, game_key, game_date)
);
CREATE TABLE IF NOT EXISTS user_stats (
    user_key TEXT PRIMARY KEY,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    total_word_points INTEGER NOT NULL DEFAULT 0,
    word_games_completed INTEGER NOT NULL DEFAULT 0,
    word_games_won INTEGER NOT NULL DEFAULT 0,
    last_completed_date TEXT,
    total_points INTEGER NOT NULL DEFAULT 0,
    games_completed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_content (
    id BIGSERIAL PRIMARY KEY,
    game_key TEXT NOT NULL,
    game_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    theme_label TEXT NOT NULL DEFAULT '',
    content_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    published_at TEXT,
    UNIQUE(game_key, game_date)
);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


class _Result:
    def __init__(self, result):
        self._result = result

    def fetchone(self):
        row = self._result.mappings().fetchone()
        return row

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


def _table_columns(_db, table):
    return {column["name"] for column in inspect(_engine()).get_columns(table)}


IDENTITY_TABLES = (
    "word_attempts",
    "mystery_attempts",
    "trivia_attempts",
    "tick_tock_attempts",
    "game_completions",
    "user_stats",
)


def _migrate_identity_columns(db):
    inspector = inspect(_engine())
    tables = set(inspector.get_table_names())
    for table in IDENTITY_TABLES:
        if table not in tables:
            continue
        columns = _table_columns(db, table)
        if "user_email" in columns and "user_key" not in columns:
            db.execute(f"ALTER TABLE {table} RENAME COLUMN user_email TO user_key")


def _migrate_game_completion_columns(db):
    if "game_completions" not in set(inspect(_engine()).get_table_names()):
        return
    columns = _table_columns(db, "game_completions")
    if "competitive" not in columns:
        db.execute("ALTER TABLE game_completions ADD COLUMN competitive INTEGER NOT NULL DEFAULT 1")


def _migrate_legacy_user_stats(db):
    if "user_stats" not in set(inspect(_engine()).get_table_names()):
        return
    columns = _table_columns(db, "user_stats")
    if "total_points" not in columns:
        db.execute("ALTER TABLE user_stats ADD COLUMN total_points INTEGER NOT NULL DEFAULT 0")
    if "games_completed" not in columns:
        db.execute("ALTER TABLE user_stats ADD COLUMN games_completed INTEGER NOT NULL DEFAULT 0")
    db.execute(
        """
        UPDATE user_stats
        SET total_points = CASE WHEN total_points = 0 THEN total_word_points ELSE total_points END,
            games_completed = CASE WHEN games_completed = 0 THEN word_games_completed ELSE games_completed END
        """
    )




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


def _recalculate_existing_streaks(db):
    if "game_completions" not in set(inspect(_engine()).get_table_names()):
        return
    users = db.execute("SELECT user_key FROM user_stats").fetchall()
    for user in users:
        rows = db.execute(
            "SELECT DISTINCT game_date FROM game_completions WHERE user_key = ? AND competitive = 1 ORDER BY game_date ASC",
            (user["user_key"],),
        ).fetchall()
        days = []
        for row in rows:
            try:
                days.append(date.fromisoformat(row["game_date"]))
            except (TypeError, ValueError):
                continue
        current_streak, longest_streak, last_date = _calculate_streaks(days)
        db.execute(
            "UPDATE user_stats SET current_streak = ?, longest_streak = ?, last_completed_date = ? WHERE user_key = ?",
            (current_streak, longest_streak, last_date, user["user_key"]),
        )


def _execute_schema(db, schema):
    for statement in schema.split(";"):
        statement = statement.strip()
        if statement:
            db.execute(statement)


def init_db():
    db = get_db()
    schema = POSTGRES_SCHEMA if _engine().dialect.name == "postgresql" else SQLITE_SCHEMA
    _execute_schema(db, schema)
    _migrate_identity_columns(db)
    _migrate_game_completion_columns(db)
    _migrate_legacy_user_stats(db)
    _recalculate_existing_streaks(db)
    db.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?) ON CONFLICT (version) DO NOTHING",
        (2, datetime.utcnow().isoformat(timespec="seconds")),
    )
    db.commit()


def ping_db():
    row = get_db().execute("SELECT 1 AS ok").fetchone()
    return bool(row and row["ok"] == 1)


def init_app(app):
    if app.config["DATABASE_URL"].startswith("sqlite:///"):
        os.makedirs(app.instance_path, exist_ok=True)
        engine = create_engine(
            app.config["DATABASE_URL"],
            future=True,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(
            app.config["DATABASE_URL"],
            future=True,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    app.extensions["crew_db_engine"] = engine
    app.teardown_appcontext(close_db)

    @app.cli.command("db-upgrade")
    def db_upgrade_command():
        """Create/upgrade the CREW database schema."""
        init_db()
        click.echo("CREW database schema is up to date.")

    if app.config.get("AUTO_DB_MIGRATE"):
        with app.app_context():
            init_db()


def ensure_user_stats(user_key):
    db = get_db()
    row = db.execute(
        "SELECT * FROM user_stats WHERE user_key = ?", (user_key,)
    ).fetchone()
    if row:
        return row

    db.execute(
        """
        INSERT INTO user_stats (
            user_key, current_streak, longest_streak, total_word_points,
            word_games_completed, word_games_won, last_completed_date,
            total_points, games_completed
        ) VALUES (?, 0, 0, 0, 0, 0, NULL, 0, 0)
        """,
        (user_key,),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM user_stats WHERE user_key = ?", (user_key,)
    ).fetchone()


# ---------- Anonymous CREW profiles ----------

def create_profile(username, password_hash, avatar, recovery_code_hash):
    db = get_db()
    created_at = datetime.utcnow().isoformat(timespec="seconds")
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
        (datetime.utcnow().isoformat(timespec="seconds"), profile_id),
    )
    db.commit()


def update_profile_credentials(profile_id, password_hash, recovery_code_hash):
    db = get_db()
    db.execute(
        """
        UPDATE profiles
        SET password_hash = ?, recovery_code_hash = ?
        WHERE id = ?
        """,
        (password_hash, recovery_code_hash, profile_id),
    )
    db.commit()


def update_profile_avatar(profile_id, avatar):
    db = get_db()
    db.execute("UPDATE profiles SET avatar = ? WHERE id = ?", (avatar, profile_id))
    db.commit()
    return get_profile_by_id(profile_id)


def update_profile_password(profile_id, password_hash):
    db = get_db()
    db.execute("UPDATE profiles SET password_hash = ? WHERE id = ?", (password_hash, profile_id))
    db.commit()


def update_profile_recovery_code(profile_id, recovery_code_hash):
    db = get_db()
    db.execute("UPDATE profiles SET recovery_code_hash = ? WHERE id = ?", (recovery_code_hash, profile_id))
    db.commit()


def profile_user_key(profile_id):
    return f"profile:{int(profile_id)}"

def load_json_list(row, column):
    try:
        value = json.loads(row[column] or "[]")
    except (TypeError, json.JSONDecodeError):
        value = []
    return value if isinstance(value, list) else []


# ---------- Word ----------

def get_or_create_word_attempt(user_key, game_date):
    db = get_db()
    row = db.execute(
        "SELECT * FROM word_attempts WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
    ).fetchone()
    if row:
        return row

    db.execute(
        "INSERT INTO word_attempts (user_key, game_date) VALUES (?, ?)",
        (user_key, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM word_attempts WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
    ).fetchone()


def load_guesses(attempt_row):
    return load_json_list(attempt_row, "guesses_json")


def save_word_attempt(user_key, game_date, guesses, completed, won, score):
    db = get_db()
    completed_at = datetime.utcnow().isoformat(timespec="seconds") if completed else None
    db.execute(
        """
        UPDATE word_attempts
        SET guesses_json = ?, completed = ?, won = ?, score = ?, completed_at = ?
        WHERE user_key = ? AND game_date = ?
        """,
        (
            json.dumps(guesses), int(completed), int(won), score, completed_at,
            user_key, game_date,
        ),
    )
    db.commit()


# ---------- Mystery ----------

def get_or_create_mystery_attempt(user_key, game_date):
    db = get_db()
    row = db.execute(
        "SELECT * FROM mystery_attempts WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO mystery_attempts (user_key, game_date) VALUES (?, ?)",
        (user_key, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM mystery_attempts WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
    ).fetchone()


def save_mystery_attempt(user_key, game_date, revealed_count, guesses, completed, won, score):
    db = get_db()
    completed_at = datetime.utcnow().isoformat(timespec="seconds") if completed else None
    db.execute(
        """
        UPDATE mystery_attempts
        SET revealed_count = ?, guesses_json = ?, completed = ?, won = ?, score = ?, completed_at = ?
        WHERE user_key = ? AND game_date = ?
        """,
        (
            revealed_count, json.dumps(guesses), int(completed), int(won), score,
            completed_at, user_key, game_date,
        ),
    )
    db.commit()


# ---------- Trivia ----------

def get_or_create_trivia_attempt(user_key, game_date):
    db = get_db()
    row = db.execute(
        "SELECT * FROM trivia_attempts WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO trivia_attempts (user_key, game_date) VALUES (?, ?)",
        (user_key, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM trivia_attempts WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
    ).fetchone()


def save_trivia_attempt(user_key, game_date, answers, completed, score):
    db = get_db()
    completed_at = datetime.utcnow().isoformat(timespec="seconds") if completed else None
    db.execute(
        """
        UPDATE trivia_attempts
        SET answers_json = ?, completed = ?, score = ?, completed_at = ?
        WHERE user_key = ? AND game_date = ?
        """,
        (json.dumps(answers), int(completed), score, completed_at, user_key, game_date),
    )
    db.commit()


# ---------- Tick-Tock ----------

def get_or_create_tick_tock_attempt(user_key, game_date, target_seconds):
    db = get_db()
    row = db.execute(
        "SELECT * FROM tick_tock_attempts WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        """
        INSERT INTO tick_tock_attempts (user_key, game_date, target_seconds)
        VALUES (?, ?, ?)
        """,
        (user_key, game_date, target_seconds),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM tick_tock_attempts WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
    ).fetchone()


def start_tick_tock_attempt(user_key, game_date):
    db = get_db()
    started_at = time.time()
    db.execute(
        """
        UPDATE tick_tock_attempts
        SET started_at = ?, stopped_at = NULL, elapsed_seconds = NULL, difference_seconds = NULL
        WHERE user_key = ? AND game_date = ? AND completed = 0
        """,
        (started_at, user_key, game_date),
    )
    db.commit()
    return started_at


def finish_tick_tock_attempt(user_key, game_date, elapsed_seconds, difference_seconds, score):
    db = get_db()
    stopped_at = time.time()
    completed_at = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        UPDATE tick_tock_attempts
        SET stopped_at = ?, elapsed_seconds = ?, difference_seconds = ?,
            completed = 1, score = ?, completed_at = ?
        WHERE user_key = ? AND game_date = ?
        """,
        (
            stopped_at, elapsed_seconds, difference_seconds, score, completed_at,
            user_key, game_date,
        ),
    )
    db.commit()


# ---------- Shared progress / scoring ----------

def finalize_game_stats(user_key, game_key, game_date, score, won=True, competitive=True):
    """Record a game completion once. Archive completions never alter competitive totals/streaks."""
    db = get_db()
    stats = ensure_user_stats(user_key)
    completed_at = datetime.utcnow().isoformat(timespec="seconds")
    cursor = db.execute(
        """
        INSERT INTO game_completions (
            user_key, game_key, game_date, score, won, completed_at, competitive
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_key, game_key, game_date) DO NOTHING
        """,
        (user_key, game_key, game_date, score, int(won), completed_at, int(bool(competitive))),
    )

    if cursor.rowcount == 0:
        return ensure_user_stats(user_key)

    if not competitive:
        db.commit()
        return ensure_user_stats(user_key)

    completion_rows = db.execute(
        "SELECT DISTINCT game_date FROM game_completions WHERE user_key = ? AND competitive = 1 ORDER BY game_date ASC",
        (user_key,),
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
        WHERE user_key = ?
        """,
        (
            current_streak, longest_streak, score, word_points, word_completed,
            word_won, last_completed_date, user_key,
        ),
    )
    db.commit()
    return ensure_user_stats(user_key)


def finalize_word_stats(user_key, game_date, won, score, competitive=True):
    return finalize_game_stats(user_key, "word", game_date, score, won, competitive=competitive)


def get_game_completion(user_key, game_key, game_date):
    return get_db().execute(
        "SELECT * FROM game_completions WHERE user_key = ? AND game_key = ? AND game_date = ?",
        (user_key, game_key, game_date),
    ).fetchone()


def get_weekly_points(user_key, reference_day=None):
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    thursday = monday.fromordinal(monday.toordinal() + 3)
    row = get_db().execute(
        """
        SELECT COALESCE(SUM(score), 0) AS points, COUNT(*) AS completed
        FROM game_completions
        WHERE user_key = ? AND competitive = 1 AND game_date BETWEEN ? AND ?
        """,
        (user_key, monday.isoformat(), thursday.isoformat()),
    ).fetchone()
    return {"points": int(row["points"]), "completed": int(row["completed"])}


def get_weekly_leaderboard(reference_day=None, limit=25):
    reference_day = reference_day or crew_today()
    monday = get_week_start(reference_day)
    thursday = monday.fromordinal(monday.toordinal() + 3)
    rows = get_db().execute(
        """
        SELECT
            p.id, p.username, p.avatar,
            COALESCE(SUM(gc.score), 0) AS points,
            COUNT(gc.id) AS completed
        FROM profiles p
        LEFT JOIN game_completions gc
            ON gc.user_key = ('profile:' || CAST(p.id AS TEXT))
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
    """Return ranked competitive standings plus game-specific performance context."""
    if game_key not in {"all", "mystery", "trivia", "word", "tick_tock"}:
        game_key = "all"
    start, end, period_label = _period_bounds(period, reference_day)
    db = get_db()
    profiles = db.execute("SELECT id, username, avatar FROM profiles ORDER BY LOWER(username)").fetchall()
    players = {
        f"profile:{int(row['id'])}": {
            "profile_id": int(row["id"]), "username": row["username"], "avatar": row["avatar"],
            "points": 0, "completed": 0, "detail": "", "secondary": None,
        }
        for row in profiles
    }

    params = []
    sql = "SELECT user_key, game_key, game_date, score, won FROM game_completions WHERE competitive = 1"
    if game_key != "all":
        sql += " AND game_key = ?"
        params.append(game_key)
    clause, date_params = _date_clause(start, end)
    sql += clause
    params.extend(date_params)
    for row in db.execute(sql, params).fetchall():
        player = players.get(row["user_key"])
        if not player:
            continue
        player["points"] += int(row["score"])
        player["completed"] += 1

    if game_key == "mystery":
        sql = """SELECT a.user_key, a.revealed_count, a.won, a.game_date FROM mystery_attempts a
                 JOIN game_completions gc ON gc.user_key = a.user_key AND gc.game_date = a.game_date
                   AND gc.game_key = 'mystery' AND gc.competitive = 1
                 WHERE a.completed = 1"""
        clause, params = _date_clause(start, end, prefix="a.game_date")
        for row in db.execute(sql + clause, params).fetchall():
            p = players.get(row["user_key"]);
            if not p: continue
            p.setdefault("clues_total", 0); p.setdefault("solved", 0); p.setdefault("metric_count", 0)
            p["clues_total"] += int(row["revealed_count"]); p["metric_count"] += 1; p["solved"] += int(row["won"])
        for p in players.values():
            if p.get("metric_count"):
                avg = p["clues_total"] / p["metric_count"]; p["secondary"] = avg
                p["detail"] = f"{p['solved']} solved · {avg:.1f} avg clues"
    elif game_key == "trivia":
        sql = """SELECT a.user_key, a.answers_json, a.game_date FROM trivia_attempts a
                 JOIN game_completions gc ON gc.user_key = a.user_key AND gc.game_date = a.game_date
                   AND gc.game_key = 'trivia' AND gc.competitive = 1
                 WHERE a.completed = 1"""
        clause, params = _date_clause(start, end, prefix="a.game_date")
        for row in db.execute(sql + clause, params).fetchall():
            p = players.get(row["user_key"]);
            if not p: continue
            try: answers = json.loads(row["answers_json"] or "[]")
            except json.JSONDecodeError: answers = []
            p.setdefault("correct", 0); p.setdefault("questions", 0)
            p["correct"] += sum(1 for a in answers if a.get("correct")); p["questions"] += len(answers)
        for p in players.values():
            if p.get("questions"):
                accuracy = (p["correct"] / p["questions"]) * 100; p["secondary"] = -accuracy
                p["detail"] = f"{accuracy:.0f}% · {p['correct']}/{p['questions']} correct"
    elif game_key == "word":
        sql = """SELECT a.user_key, a.guesses_json, a.won, a.game_date FROM word_attempts a
                 JOIN game_completions gc ON gc.user_key = a.user_key AND gc.game_date = a.game_date
                   AND gc.game_key = 'word' AND gc.competitive = 1
                 WHERE a.completed = 1"""
        clause, params = _date_clause(start, end, prefix="a.game_date")
        for row in db.execute(sql + clause, params).fetchall():
            p = players.get(row["user_key"]);
            if not p: continue
            try: guesses = json.loads(row["guesses_json"] or "[]")
            except json.JSONDecodeError: guesses = []
            p.setdefault("guess_total", 0); p.setdefault("wins", 0); p.setdefault("word_count", 0)
            p["guess_total"] += len(guesses); p["wins"] += int(row["won"]); p["word_count"] += 1
        for p in players.values():
            if p.get("word_count"):
                avg = p["guess_total"] / p["word_count"]; winrate = (p["wins"] / p["word_count"]) * 100; p["secondary"] = avg
                p["detail"] = f"{winrate:.0f}% win · {avg:.1f} avg guesses"
    elif game_key == "tick_tock":
        sql = """SELECT a.user_key, a.target_seconds, a.elapsed_seconds, a.difference_seconds, a.game_date FROM tick_tock_attempts a
                 JOIN game_completions gc ON gc.user_key = a.user_key AND gc.game_date = a.game_date
                   AND gc.game_key = 'tick_tock' AND gc.competitive = 1
                 WHERE a.completed = 1"""
        clause, params = _date_clause(start, end, prefix="a.game_date")
        for row in db.execute(sql + clause, params).fetchall():
            p = players.get(row["user_key"]);
            if not p: continue
            diff = float(row["difference_seconds"] or 0); signed = float(row["elapsed_seconds"] or 0) - float(row["target_seconds"] or 0)
            p.setdefault("diff_total", 0.0); p.setdefault("timer_count", 0); p.setdefault("best_abs", None); p.setdefault("best_signed", 0.0)
            p["diff_total"] += diff; p["timer_count"] += 1
            if p["best_abs"] is None or diff < p["best_abs"]: p["best_abs"] = diff; p["best_signed"] = signed
        for p in players.values():
            if p.get("timer_count"):
                avg = p["diff_total"] / p["timer_count"]; p["secondary"] = avg
                sign = "+" if p["best_signed"] >= 0 else "−"
                p["detail"] = f"{avg:.2f}s avg off · best {sign}{abs(p['best_signed']):.2f}s"
    else:
        for p in players.values():
            if p["completed"]:
                p["detail"] = f"{p['completed']} game{'s' if p['completed'] != 1 else ''} complete"

    ranked = [p for p in players.values() if p["points"] > 0]
    if game_key in {"mystery", "word", "tick_tock"}:
        ranked.sort(key=lambda p: (-p["points"], p["secondary"] if p["secondary"] is not None else 999999, p["username"].lower()))
    elif game_key == "trivia":
        ranked.sort(key=lambda p: (-p["points"], p["secondary"] if p["secondary"] is not None else 0, p["username"].lower()))
    else:
        ranked.sort(key=lambda p: (-p["points"], -p["completed"], p["username"].lower()))
    for idx, p in enumerate(ranked, 1):
        p["rank"] = idx; p["me"] = p["profile_id"] == current_profile_id
        for key in ("clues_total", "solved", "metric_count", "correct", "questions", "guess_total", "wins", "word_count", "diff_total", "timer_count", "best_abs", "best_signed", "secondary"):
            p.pop(key, None)
    me = next((p for p in ranked if p["me"]), None)
    if me is None and current_profile_id is not None:
        candidate = players.get(f"profile:{int(current_profile_id)}")
        if candidate:
            me = {
                "profile_id": candidate["profile_id"], "username": candidate["username"], "avatar": candidate["avatar"],
                "points": 0, "completed": 0, "detail": "No score in this view yet", "rank": None, "me": True,
            }
    return {
        "period": period, "period_label": period_label, "game": game_key,
        "players": ranked, "me": me,
        "top": ranked[:3], "total_ranked": len(ranked),
    }


def get_profile_history_summary(user_key):
    db = get_db()
    row = db.execute(
        """SELECT COUNT(*) AS completed, COALESCE(SUM(CASE WHEN competitive = 1 THEN 1 ELSE 0 END), 0) AS live_completed,
                  COALESCE(SUM(CASE WHEN competitive = 0 THEN 1 ELSE 0 END), 0) AS archive_completed
           FROM game_completions WHERE user_key = ?""", (user_key,)
    ).fetchone()
    return {"completed": int(row["completed"]), "live_completed": int(row["live_completed"]), "archive_completed": int(row["archive_completed"])}


def get_game_attempt_summary(user_key, game_key, game_date):
    db = get_db()
    table_by_key = {
        "mystery": "mystery_attempts",
        "trivia": "trivia_attempts",
        "word": "word_attempts",
        "tick_tock": "tick_tock_attempts",
    }
    table = table_by_key[game_key]
    row = db.execute(
        f"SELECT * FROM {table} WHERE user_key = ? AND game_date = ?",
        (user_key, game_date),
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

    return {
        "started": started,
        "completed": bool(row["completed"]),
        "score": int(row["score"]),
    }


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
    now = datetime.utcnow().isoformat(timespec="seconds")
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

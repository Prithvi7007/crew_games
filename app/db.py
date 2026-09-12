import json
import os
import time
from datetime import date, datetime

import click
from flask import current_app, g
from sqlalchemy import create_engine, inspect, text

from app.schedule import get_week_start, previous_scheduled_game_day


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
    _migrate_legacy_user_stats(db)
    db.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?) ON CONFLICT (version) DO NOTHING",
        (1, datetime.utcnow().isoformat(timespec="seconds")),
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

def finalize_game_stats(user_key, game_key, game_date, score, won=True):
    """Award points/streak exactly once for a scheduled CREW game."""
    db = get_db()
    stats = ensure_user_stats(user_key)
    completed_at = datetime.utcnow().isoformat(timespec="seconds")
    cursor = db.execute(
        """
        INSERT INTO game_completions (
            user_key, game_key, game_date, score, won, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_key, game_key, game_date) DO NOTHING
        """,
        (user_key, game_key, game_date, score, int(won), completed_at),
    )

    if cursor.rowcount == 0:
        return ensure_user_stats(user_key)

    try:
        game_day = date.fromisoformat(game_date)
        previous_day = date.fromisoformat(stats["last_completed_date"]) if stats["last_completed_date"] else None
    except ValueError:
        game_day = date.today()
        previous_day = None

    if previous_day == previous_scheduled_game_day(game_day):
        current_streak = stats["current_streak"] + 1
    else:
        current_streak = 1
    longest_streak = max(stats["longest_streak"], current_streak)

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
            word_won, game_date, user_key,
        ),
    )
    db.commit()
    return ensure_user_stats(user_key)


def finalize_word_stats(user_key, game_date, won, score):
    return finalize_game_stats(user_key, "word", game_date, score, won)


def get_weekly_points(user_key, reference_day=None):
    reference_day = reference_day or date.today()
    monday = get_week_start(reference_day)
    thursday = monday.fromordinal(monday.toordinal() + 3)
    row = get_db().execute(
        """
        SELECT COALESCE(SUM(score), 0) AS points, COUNT(*) AS completed
        FROM game_completions
        WHERE user_key = ? AND game_date BETWEEN ? AND ?
        """,
        (user_key, monday.isoformat(), thursday.isoformat()),
    ).fetchone()
    return {"points": int(row["points"]), "completed": int(row["completed"])}


def get_weekly_leaderboard(reference_day=None, limit=25):
    reference_day = reference_day or date.today()
    monday = get_week_start(reference_day)
    thursday = monday.fromordinal(monday.toordinal() + 3)
    rows = get_db().execute(
        """
        SELECT
            p.id,
            p.username,
            p.avatar,
            COALESCE(SUM(gc.score), 0) AS points,
            COUNT(gc.id) AS completed
        FROM profiles p
        LEFT JOIN game_completions gc
            ON gc.user_key = ('profile:' || CAST(p.id AS TEXT))
            AND gc.game_date BETWEEN ? AND ?
        GROUP BY p.id, p.username, p.avatar
        ORDER BY points DESC, completed DESC, LOWER(p.username) ASC
        LIMIT ?
        """,
        (monday.isoformat(), thursday.isoformat(), limit),
    ).fetchall()
    return [
        {
            "profile_id": row["id"],
            "username": row["username"],
            "avatar": row["avatar"],
            "points": int(row["points"]),
            "completed": int(row["completed"]),
        }
        for row in rows
    ]


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
    reference_day = reference_day or date.today()
    monday = get_week_start(reference_day)
    items = []
    for offset, game_key in enumerate(("mystery", "trivia", "word", "tick_tock")):
        game_day = monday.fromordinal(monday.toordinal() + offset)
        row = get_game_content(game_key, game_day.isoformat())
        items.append({"game_key": game_key, "game_date": game_day.isoformat(), "row": row})
    return items


def count_game_attempts(game_key, game_date):
    table_by_key = {
        "mystery": "mystery_attempts",
        "trivia": "trivia_attempts",
        "word": "word_attempts",
        "tick_tock": "tick_tock_attempts",
    }
    table = table_by_key[game_key]
    row = get_db().execute(
        f"SELECT COUNT(*) AS count FROM {table} WHERE game_date = ?",
        (game_date,),
    ).fetchone()
    return int(row["count"])

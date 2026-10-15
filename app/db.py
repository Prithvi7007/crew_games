import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import click
from flask import current_app, g
from sqlalchemy import create_engine, event, inspect, text

from app.migrations import current_revision, upgrade_database
from app.schedule import CREW_WEEK_ONE_DATE, crew_today, get_week_start, previous_scheduled_game_day


class ConcurrentAttemptError(RuntimeError):
    """Another request already changed or completed this game attempt."""


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
    # Migration preflights must not use the request-scoped get_db() connection.
    # Flask keeps that connection in ``g`` until the CLI app context exits, which
    # means its read transaction can remain open while Alembic starts DDL on a
    # second connection. PostgreSQL then correctly blocks the ALTER TABLE behind
    # the preflight transaction. Keep the preflight fully self-contained instead.
    engine = _engine()
    with engine.connect() as connection:
        db = _Connection(connection)
        tables = set(inspect(connection).get_table_names())
        profile_ids = (
            {int(row["id"]) for row in db.execute("SELECT id FROM profiles").fetchall()}
            if "profiles" in tables
            else set()
        )
        issues = []
        for table in (
            "word_attempts",
            "mystery_attempts",
            "trivia_attempts",
            "tick_tock_attempts",
            "game_completions",
            "user_stats",
        ):
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


PROFILE_ROLES = {"player", "admin", "owner"}


def update_profile_role(profile_id, role):
    role = str(role or "").strip().lower()
    if role not in PROFILE_ROLES:
        raise ValueError("Invalid CREW profile role")
    db = get_db()
    db.execute(
        "UPDATE profiles SET role = ?, session_version = session_version + 1 WHERE id = ?",
        (role, int(profile_id)),
    )
    db.commit()
    return get_profile_by_id(profile_id)


def delete_profile(profile_id):
    db = get_db()
    result = db.execute("DELETE FROM profiles WHERE id = ?", (int(profile_id),))
    db.commit()
    return result.rowcount > 0


def get_setting(setting_key):
    row = get_db().execute(
        "SELECT setting_value FROM system_settings WHERE setting_key = ?",
        (str(setting_key),),
    ).fetchone()
    return row["setting_value"] if row else None


def set_setting(setting_key, setting_value):
    db = get_db()
    db.execute(
        """
        INSERT INTO system_settings (setting_key, setting_value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT (setting_key) DO UPDATE SET
            setting_value = excluded.setting_value,
            updated_at = excluded.updated_at
        """,
        (str(setting_key), str(setting_value), _db_timestamp()),
    )
    db.commit()


def profile_user_key(profile_id):
    return f"profile:{int(profile_id)}"


# ---------- Seasons ----------

def _season_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid season date") from exc


def _season_payload(row, reference_day=None):
    if not row:
        return None
    reference_day = reference_day or crew_today()
    start_date = _season_date(row["start_date"])
    end_date = _season_date(row["end_date"])
    season_start_week = get_week_start(start_date)
    season_end_week = get_week_start(end_date)
    weeks_total = ((season_end_week - season_start_week).days // 7) + 1
    current_week = get_week_start(reference_day)
    week_number = ((current_week - season_start_week).days // 7) + 1
    week_number = max(1, min(weeks_total, week_number))
    status = (
        "active"
        if start_date <= reference_day <= end_date
        else ("upcoming" if reference_day < start_date else "complete")
    )
    return {
        "id": int(row["id"]),
        "number": int(row["season_number"]),
        "slug": row["slug"],
        "name": row["name"],
        "start_date": start_date,
        "end_date": end_date,
        "week_number": week_number,
        "weeks_total": weeks_total,
        "games_total": weeks_total * 4,
        "max_points": weeks_total * 400,
        "status": status,
        "has_results": bool(row["has_results"]),
        "dates_locked": bool(row["has_results"]),
    }


def list_seasons(reference_day=None):
    rows = get_db().execute(
        """
        SELECT s.*,
               EXISTS(
                   SELECT 1
                   FROM game_completions gc
                   WHERE gc.competitive = 1
                     AND gc.game_date BETWEEN s.start_date AND s.end_date
               ) AS has_results
        FROM seasons s
        ORDER BY s.season_number DESC
        """
    ).fetchall()
    return [_season_payload(row, reference_day=reference_day) for row in rows]


def get_season_by_id(season_id, reference_day=None):
    row = get_db().execute(
        """
        SELECT s.*,
               EXISTS(
                   SELECT 1
                   FROM game_completions gc
                   WHERE gc.competitive = 1
                     AND gc.game_date BETWEEN s.start_date AND s.end_date
               ) AS has_results
        FROM seasons s
        WHERE s.id = ?
        """,
        (int(season_id),),
    ).fetchone()
    return _season_payload(row, reference_day=reference_day) if row else None


def get_season_for_date(reference_day=None):
    reference_day = reference_day or crew_today()
    day_iso = reference_day.isoformat()
    row = get_db().execute(
        """
        SELECT s.*,
               EXISTS(
                   SELECT 1
                   FROM game_completions gc
                   WHERE gc.competitive = 1
                     AND gc.game_date BETWEEN s.start_date AND s.end_date
               ) AS has_results
        FROM seasons s
        WHERE s.start_date <= ? AND s.end_date >= ?
        ORDER BY s.season_number DESC
        LIMIT 1
        """,
        (day_iso, day_iso),
    ).fetchone()
    return _season_payload(row, reference_day=reference_day) if row else None


def _validate_season_overlap(start_date, end_date, exclude_id=None):
    sql = """
        SELECT id, season_number, name
        FROM seasons
        WHERE NOT (end_date < ? OR start_date > ?)
    """
    params = [start_date.isoformat(), end_date.isoformat()]
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(int(exclude_id))
    return get_db().execute(sql, params).fetchone()


def create_season(name, start_date, end_date):
    name = str(name or "").strip()
    start_date = _season_date(start_date)
    end_date = _season_date(end_date)
    if not name:
        raise ValueError("Season name is required.")
    if _validate_season_overlap(start_date, end_date):
        raise ValueError("Season dates overlap an existing season.")

    db = get_db()
    row = db.execute(
        "SELECT COALESCE(MAX(season_number), 0) AS max_number FROM seasons"
    ).fetchone()
    season_number = int(row["max_number"]) + 1
    slug = f"season-{season_number}"
    db.execute(
        """
        INSERT INTO seasons (season_number, slug, name, start_date, end_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            season_number,
            slug,
            name,
            start_date.isoformat(),
            end_date.isoformat(),
            _db_timestamp(),
        ),
    )
    db.commit()
    created = db.execute(
        "SELECT id FROM seasons WHERE season_number = ?",
        (season_number,),
    ).fetchone()
    return get_season_by_id(created["id"])


def update_season(season_id, name, start_date, end_date):
    season = get_season_by_id(season_id)
    if not season:
        raise ValueError("Season not found.")

    name = str(name or "").strip()
    start_date = _season_date(start_date)
    end_date = _season_date(end_date)
    if not name:
        raise ValueError("Season name is required.")

    dates_changed = (
        start_date != season["start_date"]
        or end_date != season["end_date"]
    )
    if dates_changed and season["dates_locked"]:
        raise ValueError("Season dates are locked because competitive results already exist.")
    # A finalized award snapshot cannot be reinterpreted under new dates.
    if dates_changed and get_db().execute(
        "SELECT 1 FROM season_badge_finalizations WHERE season_id = ?",
        (int(season_id),),
    ).fetchone():
        raise ValueError("Season dates are locked after championship finalization.")
    if _validate_season_overlap(start_date, end_date, exclude_id=season_id):
        raise ValueError("Season dates overlap an existing season.")

    db = get_db()
    db.execute(
        """
        UPDATE seasons
        SET name = ?, start_date = ?, end_date = ?
        WHERE id = ?
        """,
        (name, start_date.isoformat(), end_date.isoformat(), int(season_id)),
    )
    db.commit()
    return get_season_by_id(season_id)


def get_season_summary(user_key, reference_day=None):
    profile_id = _profile_id_from_user_key(user_key)
    season = get_season_for_date(reference_day)
    if not season:
        return None

    db = get_db()
    start_iso = season["start_date"].isoformat()
    end_iso = season["end_date"].isoformat()
    row = db.execute(
        """
        SELECT COALESCE(SUM(score), 0) AS points, COUNT(*) AS completed
        FROM game_completions
        WHERE profile_id = ?
          AND game_date BETWEEN ? AND ?
        """,
        (profile_id, start_iso, end_iso),
    ).fetchone()

    rank_row = db.execute(
        """
        WITH season_scores AS (
            SELECT
                p.id AS profile_id,
                p.username,
                COALESCE(SUM(gc.score), 0) AS points,
                COUNT(gc.id) AS completed
            FROM profiles p
            LEFT JOIN game_completions gc
              ON gc.profile_id = p.id
             AND gc.game_date BETWEEN ? AND ?
            GROUP BY p.id, p.username
        ), ranked AS (
            SELECT
                profile_id,
                ROW_NUMBER() OVER (
                    ORDER BY points DESC, completed DESC, LOWER(username) ASC
                ) AS rank
            FROM season_scores
            WHERE points > 0
        )
        SELECT rank
        FROM ranked
        WHERE profile_id = ?
        """,
        (start_iso, end_iso, profile_id),
    ).fetchone()

    result = dict(season)
    result.update(
        {
            "points": int(row["points"]),
            "completed": int(row["completed"]),
            "rank": int(rank_row["rank"]) if rank_row else None,
        }
    )
    return result


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


# Gameplay storage and scoring live in a dedicated module, with stable imports.
from app.db_gameplay import (
    load_json_list,
    get_or_create_word_attempt,
    load_guesses,
    save_word_attempt,
    get_or_create_mystery_attempt,
    save_mystery_attempt,
    get_or_create_trivia_attempt,
    save_trivia_attempt,
    get_or_create_tick_tock_attempt,
    start_tick_tock_attempt,
    finish_tick_tock_attempt,
    finalize_game_stats,
    finalize_word_stats,
    get_game_completion,
)


# Read-side queries live in a dedicated module; retain the public import API.
from app.db_leaderboards import (
    get_weekly_points,
    get_weekly_leaderboard,
    get_rankings_between,
    get_competitive_rankings_between,
    get_home_leaderboard,
    _period_bounds,
    _date_clause,
    get_leaderboard,
    get_championship_score_rows,
)


def get_profile_history_summary(user_key):
    profile_id = _profile_id_from_user_key(user_key)
    row = get_db().execute(
        """SELECT COUNT(*) AS completed,
                  COALESCE(SUM(CASE WHEN competitive = 1 THEN 1 ELSE 0 END), 0) AS live_completed,
                  COALESCE(SUM(CASE WHEN competitive = 0 THEN 1 ELSE 0 END), 0) AS archive_completed
           FROM game_completions
           WHERE profile_id = ? AND game_date >= ?""",
        (profile_id, CREW_WEEK_ONE_DATE.isoformat()),
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

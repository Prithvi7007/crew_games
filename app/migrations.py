from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect, text

BASELINE_REVISION = "v11_baseline"
HEAD_REVISION = "v12_platform"
ROOT = Path(__file__).resolve().parents[1]


def _normalize_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


def alembic_config(database_url: str) -> AlembicConfig:
    cfg = AlembicConfig(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    # ConfigParser treats % as interpolation, so escape it for URL-encoded passwords.
    cfg.set_main_option("sqlalchemy.url", _normalize_url(database_url).replace("%", "%%"))
    return cfg


def _schema_state(database_url: str) -> tuple[bool, bool, list[str]]:
    engine = create_engine(_normalize_url(database_url), future=True, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            has_version = "alembic_version" in tables
            has_legacy_schema = "profiles" in tables
            if has_version or not has_legacy_schema:
                return has_version, has_legacy_schema, []

            # Never stamp an arbitrary pre-Alembic database as v11. A stamp tells
            # Alembic that the entire baseline already exists, so verify the v11
            # security/schema markers first and fail closed if they do not.
            missing = []
            required_tables = {
                "profiles", "word_games", "word_attempts", "mystery_attempts",
                "trivia_attempts", "tick_tock_attempts", "game_completions",
                "user_stats", "game_content", "security_rate_limits",
                "security_events", "schema_migrations",
            }
            missing.extend(f"table:{name}" for name in sorted(required_tables - tables))
            if "profiles" in tables:
                profile_columns = {column["name"] for column in inspector.get_columns("profiles")}
                if "session_version" not in profile_columns:
                    missing.append("column:profiles.session_version")
            if "game_completions" in tables:
                completion_columns = {
                    column["name"] for column in inspector.get_columns("game_completions")
                }
                if "competitive" not in completion_columns:
                    missing.append("column:game_completions.competitive")
            return has_version, has_legacy_schema, missing
    finally:
        engine.dispose()


def upgrade_database(database_url: str, revision: str = "head") -> None:
    cfg = alembic_config(database_url)
    has_version, has_legacy_schema, baseline_gaps = _schema_state(database_url)
    if not has_version and has_legacy_schema:
        if baseline_gaps:
            raise RuntimeError(
                "Unversioned database does not match the CREW v11.0.1 baseline; "
                "upgrade to v11.0.1 before v12. Missing: " + ", ".join(baseline_gaps)
            )
        # v11 and earlier predate Alembic. Stamp only after verifying the complete
        # v11.0.1 baseline, then run the additive v12 migration. Existing rows are
        # not recreated.
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, revision)


def current_revision(database_url: str) -> str | None:
    engine = create_engine(_normalize_url(database_url), future=True, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            if "alembic_version" not in set(inspect(connection).get_table_names()):
                return None
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    finally:
        engine.dispose()

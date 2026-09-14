"""CREW v11.0.1 schema baseline.

Revision ID: v11_baseline
Revises: None
"""
from alembic import op
import sqlalchemy as sa

revision = "v11_baseline"
down_revision = None
branch_labels = None
depends_on = None

ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("avatar", sa.Text(), nullable=False),
        sa.Column("recovery_code_hash", sa.Text(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("last_login_at", sa.Text()),
    )
    op.create_index("ux_profiles_username_lower", "profiles", [sa.text("lower(username)")], unique=True)

    op.create_table(
        "word_games",
        sa.Column("game_date", sa.Text(), primary_key=True),
        sa.Column("solution", sa.Text(), nullable=False),
    )

    for table, extra in (
        ("word_attempts", [
            sa.Column("guesses_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("won", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_at", sa.Text()),
        ]),
        ("mystery_attempts", [
            sa.Column("revealed_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("guesses_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("won", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_at", sa.Text()),
        ]),
        ("trivia_attempts", [
            sa.Column("answers_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_at", sa.Text()),
        ]),
        ("tick_tock_attempts", [
            sa.Column("target_seconds", sa.Float(), nullable=False),
            sa.Column("started_at", sa.Float()),
            sa.Column("stopped_at", sa.Float()),
            sa.Column("elapsed_seconds", sa.Float()),
            sa.Column("difference_seconds", sa.Float()),
            sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_at", sa.Text()),
        ]),
    ):
        op.create_table(
            table,
            sa.Column("id", ID, primary_key=True, autoincrement=True),
            sa.Column("user_key", sa.Text(), nullable=False),
            sa.Column("game_date", sa.Text(), nullable=False),
            *extra,
            sa.UniqueConstraint("user_key", "game_date", name=f"uq_{table}_user_date"),
        )

    op.create_table(
        "game_completions",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("game_key", sa.Text(), nullable=False),
        sa.Column("game_date", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("won", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("completed_at", sa.Text(), nullable=False),
        sa.Column("competitive", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("user_key", "game_key", "game_date", name="uq_game_completions_user_game_date"),
    )

    op.create_table(
        "user_stats",
        sa.Column("user_key", sa.Text(), primary_key=True),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_word_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("word_games_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("word_games_won", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_completed_date", sa.Text()),
        sa.Column("total_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("games_completed", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "game_content",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("game_key", sa.Text(), nullable=False),
        sa.Column("game_date", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("theme_label", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("published_at", sa.Text()),
        sa.UniqueConstraint("game_key", "game_date", name="uq_game_content_game_date"),
    )

    op.create_table(
        "security_rate_limits",
        sa.Column("limiter_key", sa.Text(), primary_key=True),
        sa.Column("window_started_at", sa.BigInteger(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "security_events",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("subject_hash", sa.Text(), nullable=False, server_default=""),
        sa.Column("ip_hash", sa.Text(), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_security_events_occurred_at", "security_events", ["occurred_at"])

    op.create_table(
        "schema_migrations",
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("applied_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "schema_migrations", "security_events", "security_rate_limits", "game_content",
        "user_stats", "game_completions", "tick_tock_attempts", "trivia_attempts",
        "mystery_attempts", "word_attempts", "word_games", "profiles",
    ):
        op.drop_table(table)

"""CREW v12 platform integrity and performance migration.

Revision ID: v12_platform
Revises: v11_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = "v12_platform"
down_revision = "v11_baseline"
branch_labels = None
depends_on = None

IDENTITY_TABLES = (
    "word_attempts",
    "mystery_attempts",
    "trivia_attempts",
    "tick_tock_attempts",
    "game_completions",
    "user_stats",
)


def _profile_type(dialect: str):
    return sa.Integer() if dialect == "sqlite" else sa.BigInteger()


def _backfill_profile_id(table: str, dialect: str) -> None:
    if dialect == "postgresql":
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET profile_id = CAST(split_part(user_key, ':', 2) AS BIGINT)
                WHERE user_key ~ '^profile:[0-9]+$'
                """
            )
        )
    else:
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET profile_id = CAST(substr(user_key, 9) AS INTEGER)
                WHERE user_key GLOB 'profile:[0-9]*'
                """
            )
        )

    bind = op.get_bind()
    invalid = bind.execute(
        sa.text(
            f"""
            SELECT COUNT(*)
            FROM {table} t
            LEFT JOIN profiles p ON p.id = t.profile_id
            WHERE t.profile_id IS NULL OR p.id IS NULL
            """
        )
    ).scalar_one()
    if invalid:
        raise RuntimeError(
            f"Cannot migrate {table}: {invalid} row(s) do not map to an existing profile. "
            "Run the v12 db-integrity-check before upgrading."
        )


def _create_profile_sync_trigger(table: str, dialect: str) -> None:
    if dialect == "postgresql":
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_profile_id_sync ON {table}"))
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table}_profile_id_sync
                BEFORE INSERT OR UPDATE OF user_key, profile_id ON {table}
                FOR EACH ROW EXECUTE FUNCTION crew_sync_profile_id()
                """
            )
        )
    else:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_profile_id_sync"))
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table}_profile_id_sync
                AFTER INSERT ON {table}
                WHEN NEW.profile_id IS NULL AND NEW.user_key GLOB 'profile:[0-9]*'
                BEGIN
                    UPDATE {table}
                    SET profile_id = CAST(substr(NEW.user_key, 9) AS INTEGER)
                    WHERE rowid = NEW.rowid;
                END
                """
            )
        )


def _make_profile_relation(table: str, dialect: str) -> None:
    fk_name = f"fk_{table}_profile_id_profiles"
    uq_name = "uq_user_stats_profile_id" if table == "user_stats" else (
        "uq_game_completions_profile_game_date"
        if table == "game_completions"
        else f"uq_{table}_profile_date"
    )
    unique_cols = ["profile_id"] if table == "user_stats" else (
        ["profile_id", "game_key", "game_date"]
        if table == "game_completions"
        else ["profile_id", "game_date"]
    )

    if dialect == "sqlite":
        with op.batch_alter_table(table, recreate="always") as batch:
            # SQLite keeps this nullable during the expand phase so an older local
            # app build can still be used for emergency rollback. Production
            # PostgreSQL uses a compatibility trigger plus NOT NULL.
            batch.create_foreign_key(fk_name, "profiles", ["profile_id"], ["id"], ondelete="CASCADE")
            batch.create_unique_constraint(uq_name, unique_cols)
            batch.create_check_constraint(
                f"ck_{table}_profile_key",
                "user_key GLOB 'profile:[0-9]*' AND (profile_id IS NULL OR user_key = ('profile:' || CAST(profile_id AS TEXT)))",
            )
            if table == "game_completions":
                batch.create_check_constraint(
                    "ck_game_completions_game_key",
                    "game_key IN ('mystery','trivia','word','tick_tock')",
                )
                batch.create_check_constraint("ck_game_completions_score", "score BETWEEN 0 AND 100")
                batch.create_check_constraint("ck_game_completions_won", "won IN (0,1)")
                batch.create_check_constraint("ck_game_completions_competitive", "competitive IN (0,1)")
    else:
        op.alter_column(table, "profile_id", existing_type=sa.BigInteger(), nullable=False)
        op.create_foreign_key(fk_name, table, "profiles", ["profile_id"], ["id"], ondelete="CASCADE")
        op.create_unique_constraint(uq_name, table, unique_cols)
        op.create_check_constraint(
            f"ck_{table}_profile_key", table,
            "user_key = ('profile:' || CAST(profile_id AS TEXT))",
        )
        if table == "game_completions":
            op.create_check_constraint(
                "ck_game_completions_game_key", table,
                "game_key IN ('mystery','trivia','word','tick_tock')",
            )
            op.create_check_constraint("ck_game_completions_score", table, "score BETWEEN 0 AND 100")
            op.create_check_constraint("ck_game_completions_won", table, "won IN (0,1)")
            op.create_check_constraint("ck_game_completions_competitive", table, "competitive IN (0,1)")


def _add_content_checks(dialect: str) -> None:
    if dialect == "sqlite":
        with op.batch_alter_table("game_content", recreate="always") as batch:
            batch.create_check_constraint(
                "ck_game_content_game_key",
                "game_key IN ('mystery','trivia','word','tick_tock')",
            )
            batch.create_check_constraint("ck_game_content_status", "status IN ('draft','published')")
    else:
        op.create_check_constraint(
            "ck_game_content_game_key", "game_content",
            "game_key IN ('mystery','trivia','word','tick_tock')",
        )
        op.create_check_constraint(
            "ck_game_content_status", "game_content", "status IN ('draft','published')"
        )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                CREATE OR REPLACE FUNCTION crew_sync_profile_id() RETURNS trigger AS $$
                DECLARE derived_profile_id BIGINT;
                BEGIN
                    IF NEW.user_key !~ '^profile:[0-9]+$' THEN
                        RAISE EXCEPTION 'invalid CREW profile key: %', NEW.user_key;
                    END IF;
                    derived_profile_id := CAST(split_part(NEW.user_key, ':', 2) AS BIGINT);
                    IF NEW.profile_id IS NULL THEN
                        NEW.profile_id := derived_profile_id;
                    ELSIF NEW.profile_id <> derived_profile_id THEN
                        RAISE EXCEPTION 'profile_id does not match user_key';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )

    for table in IDENTITY_TABLES:
        op.add_column(table, sa.Column("profile_id", _profile_type(dialect), nullable=True))
        _backfill_profile_id(table, dialect)
        _make_profile_relation(table, dialect)
        _create_profile_sync_trigger(table, dialect)

    _add_content_checks(dialect)

    op.create_index(
        "ix_game_completions_comp_date_game_profile",
        "game_completions",
        ["competitive", "game_date", "game_key", "profile_id"],
    )
    op.create_index(
        "ix_game_completions_profile_date_comp",
        "game_completions",
        ["profile_id", "game_date", "competitive"],
    )
    op.create_index(
        "ix_game_content_status_date_game",
        "game_content",
        ["status", "game_date", "game_key"],
    )
    op.create_index(
        "ix_security_rate_limits_window_started",
        "security_rate_limits",
        ["window_started_at"],
    )
    op.create_index(
        "ix_security_events_type_occurred",
        "security_events",
        ["event_type", "occurred_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for index_name, table in (
        ("ix_security_events_type_occurred", "security_events"),
        ("ix_security_rate_limits_window_started", "security_rate_limits"),
        ("ix_game_content_status_date_game", "game_content"),
        ("ix_game_completions_profile_date_comp", "game_completions"),
        ("ix_game_completions_comp_date_game_profile", "game_completions"),
    ):
        op.drop_index(index_name, table_name=table)

    if dialect == "sqlite":
        with op.batch_alter_table("game_content", recreate="always") as batch:
            batch.drop_constraint("ck_game_content_status", type_="check")
            batch.drop_constraint("ck_game_content_game_key", type_="check")
    else:
        op.drop_constraint("ck_game_content_status", "game_content", type_="check")
        op.drop_constraint("ck_game_content_game_key", "game_content", type_="check")

    for table in reversed(IDENTITY_TABLES):
        fk_name = f"fk_{table}_profile_id_profiles"
        uq_name = "uq_user_stats_profile_id" if table == "user_stats" else (
            "uq_game_completions_profile_game_date"
            if table == "game_completions"
            else f"uq_{table}_profile_date"
        )
        if dialect == "sqlite":
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_profile_id_sync"))
            with op.batch_alter_table(table, recreate="always") as batch:
                if table == "game_completions":
                    batch.drop_constraint("ck_game_completions_competitive", type_="check")
                    batch.drop_constraint("ck_game_completions_won", type_="check")
                    batch.drop_constraint("ck_game_completions_score", type_="check")
                    batch.drop_constraint("ck_game_completions_game_key", type_="check")
                batch.drop_constraint(f"ck_{table}_profile_key", type_="check")
                batch.drop_constraint(uq_name, type_="unique")
                batch.drop_constraint(fk_name, type_="foreignkey")
                batch.drop_column("profile_id")
        else:
            if table == "game_completions":
                for name in (
                    "ck_game_completions_competitive",
                    "ck_game_completions_won",
                    "ck_game_completions_score",
                    "ck_game_completions_game_key",
                ):
                    op.drop_constraint(name, table, type_="check")
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_profile_id_sync ON {table}"))
            op.drop_constraint(f"ck_{table}_profile_key", table, type_="check")
            op.drop_constraint(uq_name, table, type_="unique")
            op.drop_constraint(fk_name, table, type_="foreignkey")
            op.drop_column(table, "profile_id")

    if dialect == "postgresql":
        op.execute(sa.text("DROP FUNCTION IF EXISTS crew_sync_profile_id()"))

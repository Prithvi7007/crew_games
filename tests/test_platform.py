from pathlib import Path
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from app.db import (
    create_profile,
    ensure_user_stats,
    finalize_game_stats,
    get_game_completion,
    profile_user_key,
)
from app.migrations import HEAD_REVISION, current_revision


def _profile(app, username="PlatformTester"):
    with app.app_context():
        profile = create_profile(
            username,
            generate_password_hash("correct horse battery staple"),
            "⭐",
            generate_password_hash("ORBIT-NOVA-COMET-RIVER-ABCD"),
        )
        return int(profile["id"])


def test_database_is_at_v12_revision(app):
    assert current_revision(app.config["DATABASE_URL"]) == HEAD_REVISION


def test_profile_foreign_keys_and_indexes_exist(app):
    with app.app_context():
        engine = app.extensions["crew_db_engine"]
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("game_completions")}
        assert "profile_id" in columns
        foreign_keys = inspector.get_foreign_keys("game_completions")
        assert any(
            fk["referred_table"] == "profiles" and fk["constrained_columns"] == ["profile_id"]
            for fk in foreign_keys
        )
        indexes = {index["name"] for index in inspector.get_indexes("game_completions")}
        assert "ix_game_completions_comp_date_game_profile" in indexes
        assert "ix_game_completions_profile_date_comp" in indexes


def test_new_game_rows_use_relational_profile_id(app):
    profile_id = _profile(app)
    user_key = profile_user_key(profile_id)
    with app.app_context():
        finalize_game_stats(user_key, "word", "2026-09-23", 100, True, competitive=True)
        row = get_game_completion(user_key, "word", "2026-09-23")
        assert row["profile_id"] == profile_id
        assert row["user_key"] == user_key


def test_request_id_and_health_endpoints(client):
    response = client.get("/health/live", headers={"X-Request-ID": "test-request-1234"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-1234"
    assert response.get_json()["version"] == "12.0.0"

    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.headers.get("X-Request-ID")


def test_expand_migration_keeps_v11_style_writes_compatible(app):
    profile_id = _profile(app, username="RollbackTester")
    user_key = profile_user_key(profile_id)
    with app.app_context():
        from app.db import get_db
        db = get_db()
        # Simulate the previous v11 INSERT shape, which did not know profile_id.
        db.execute(
            """
            INSERT INTO game_completions
                (user_key, game_key, game_date, score, won, completed_at, competitive)
            VALUES (?, 'word', '2026-09-16', 80, 1, '2026-09-16T12:00:00', 1)
            """,
            (user_key,),
        )
        db.commit()
        row = db.execute(
            "SELECT profile_id FROM game_completions WHERE user_key = ? AND game_date = '2026-09-16'",
            (user_key,),
        ).fetchone()
        assert row["profile_id"] == profile_id


def test_home_leaderboard_returns_top_three_plus_current_rank(app):
    from datetime import date
    from app.db import get_home_leaderboard

    ids = []
    for username in ("Alpha", "Beta", "Gamma", "Delta"):
        ids.append(_profile(app, username=username))

    with app.app_context():
        for profile_id, score in zip(ids, (100, 90, 80, 70)):
            finalize_game_stats(
                profile_user_key(profile_id),
                "word",
                "2026-09-23",
                score,
                True,
                competitive=True,
            )
        rows = get_home_leaderboard(date(2026, 9, 23), current_profile_id=ids[3])

    assert [row["rank"] for row in rows] == [1, 2, 3, 4]
    assert [row["profile_id"] for row in rows] == ids
    assert rows[-1]["me"] is True


def test_unversioned_pre_v11_schema_is_rejected(tmp_path):
    import pytest
    from sqlalchemy import create_engine, text
    from app.migrations import upgrade_database

    database_url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE profiles (id INTEGER PRIMARY KEY, username TEXT NOT NULL)"))
    engine.dispose()

    with pytest.raises(RuntimeError, match="v11\\.0\\.1 baseline"):
        upgrade_database(database_url)

def test_profile_exposes_sign_out_action(app):
    profile_id = _profile(app, username="SignoutTester")
    client = app.test_client()
    with client.session_transaction() as session:
        session["user"] = {
            "profile_id": profile_id,
            "username": "SignoutTester",
            "avatar": "⭐",
            "user_key": profile_user_key(profile_id),
            "session_version": 1,
        }

    response = client.get("/profile")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'id="crew-player-root"' in html
    assert 'data-page="profile"' in html
    assert "/static/react/player.js" in html

    # React bootstrap data must never expose credential or internal session fields.
    for forbidden in (
        "password_hash",
        "recovery_code_hash",
        "session_version",
        "user_key",
        "profile_id",
    ):
        assert forbidden not in html

    react = (
        Path(__file__).parents[1]
        / "frontend"
        / "src"
        / "player"
        / "main.jsx"
    ).read_text(encoding="utf-8")

    assert 'action="/logout"' in react
    assert 'name="csrf_token"' in react



def test_global_account_menu_exposes_profile_and_sign_out():
    root = Path(__file__).parents[1]
    source = (
        root / "frontend" / "src" / "player" / "main.jsx"
    ).read_text(encoding="utf-8")

    assert "function AccountMenu" in source
    assert 'aria-haspopup="menu"' in source
    assert 'href="/profile"' in source
    assert 'action="/logout"' in source
    assert ">Sign out<" in source
    assert "function AppHeader" in source

def test_db_upgrade_releases_preflight_connection_before_alembic(app, monkeypatch):
    import app.db as db_module
    from flask import g

    observed = {}

    def fake_upgrade(_database_url):
        observed["request_scoped_connection_open"] = "db" in g

    monkeypatch.setattr(db_module, "upgrade_database", fake_upgrade)
    runner = app.test_cli_runner()
    result = runner.invoke(args=["db-upgrade"])

    assert result.exit_code == 0, result.output
    assert observed["request_scoped_connection_open"] is False

def test_crew_week_number_starts_with_curated_bank_launch():
    from datetime import date
    from app.schedule import get_crew_week_number

    assert get_crew_week_number(date(2026, 9, 20)) == 0
    assert get_crew_week_number(date(2026, 9, 21)) == 1
    assert get_crew_week_number(date(2026, 9, 27)) == 1
    assert get_crew_week_number(date(2026, 9, 28)) == 2
    assert get_crew_week_number(date(2026, 10, 5)) == 3


def test_archive_games_score_but_do_not_qualify_for_streaks():
    from datetime import date
    from app.schedule import game_is_archive, game_is_competitive

    today = date(2026, 9, 28)
    old_game = date(2026, 9, 21)
    assert game_is_archive(old_game, today=today) is True
    assert game_is_competitive(old_game, today=today) is False
    assert game_is_competitive(date(2026, 9, 28), today=today) is True
    assert game_is_competitive(date(2026, 9, 29), today=today) is False

def test_archive_completion_counts_points_in_original_week(app):
    from datetime import date
    from app.db import get_weekly_points
    from app.schedule import game_is_competitive

    profile_id = _profile(app, username="ArchiveScorer")
    user_key = profile_user_key(profile_id)
    game_day = date(2026, 9, 21)

    with app.app_context():
        finalize_game_stats(
            user_key,
            "mystery",
            game_day.isoformat(),
            75,
            True,
            competitive=game_is_competitive(game_day, today=date(2026, 9, 28)),
        )
        weekly = get_weekly_points(user_key, game_day)
        stats = ensure_user_stats(user_key)
        assert weekly["points"] == 75
        assert weekly["completed"] == 1
        assert stats["total_points"] == 75
        assert stats["games_completed"] == 1
        assert stats["current_streak"] == 0
        assert stats["longest_streak"] == 0

def test_archive_play_banners_are_removed_from_game_templates():
    root = Path(__file__).parents[1]
    source = (
        root / "frontend" / "src" / "player" / "main.jsx"
    ).read_text(encoding="utf-8")

    assert "Archive play" not in source

def test_tick_tock_page_explains_scoring_ladder():
    root = Path(__file__).parents[1]
    source = (
        root / "frontend" / "src" / "player" / "main.jsx"
    ).read_text(encoding="utf-8")

    assert "HOW IT SCORES" in source
    for label, score in (
        ("Within 0.10 sec", "100"),
        ("Within 0.25 sec", "90"),
        ("Within 0.50 sec", "80"),
        ("Within 1.00 sec", "60"),
        ("Within 1.50 sec", "40"),
        ("Within 2.50 sec", "20"),
        ("More than 2.50 sec", "10"),
    ):
        assert label in source
        assert score in source

def test_mystery_unsolved_completion_awards_participation_points():
    root = Path(__file__).parents[1]

    routes = (root / "app/mystery/routes.py").read_text(encoding="utf-8")
    player = (
        root / "frontend" / "src" / "player" / "main.jsx"
    ).read_text(encoding="utf-8")
    admin_test = (
        root / "app/static/js/v2-admin-test.js"
    ).read_text(encoding="utf-8")

    assert "score, completed = 10, True" in routes
    assert "Unsolved" in player
    assert "10 participation points" in player
    assert "<strong>10</strong><small>PTS · ANSWER" in admin_test

def test_future_player_game_urls_redirect_without_loading_attempts(app, monkeypatch):
    from datetime import date
    import app.schedule as schedule
    from app.db import get_db, get_profile_by_id

    profile_id = _profile(app, username="FutureGuardTester")
    user_key = profile_user_key(profile_id)
    with app.app_context():
        profile = get_profile_by_id(profile_id)

    client = app.test_client()
    client.get("/login")
    with client.session_transaction() as session:
        session["user"] = {
            "profile_id": profile_id,
            "username": profile["username"],
            "avatar": profile["avatar"],
            "role": profile["role"],
            "user_key": user_key,
            "session_version": int(profile["session_version"]),
        }

    monkeypatch.setattr(schedule, "crew_today", lambda: date(2026, 9, 20))

    for url in (
        "/mystery?date=2026-09-21",
        "/trivia?date=2026-09-22",
        "/word?date=2026-09-23",
        "/tick-tock?date=2026-09-24",
    ):
        response = client.get(url)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/games")

    with app.app_context():
        for table in ("mystery_attempts", "trivia_attempts", "word_attempts", "tick_tock_attempts"):
            row = get_db().execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            assert int(row["count"]) == 0


def test_games_page_copy_matches_catch_up_scoring_rules():
    root = Path(__file__).parents[1]
    source = (
        root / "frontend" / "src" / "player" / "main.jsx"
    ).read_text(encoding="utf-8")

    assert "Past leaderboards stay locked." not in source
    assert "Catch-up scores count toward the week" in source
    assert "Catch-up play does not create, extend, or repair a streak." in source

def test_rankings_empty_state_respects_hidden_attribute():
    root = Path(__file__).parents[1]
    css = (
        root / "frontend/src/player/styles/rankings.css"
    ).read_text(encoding="utf-8")
    source = (
        root / "frontend/src/player/main.jsx"
    ).read_text(encoding="utf-8")

    assert ".rankings-empty[hidden]" in css
    assert "display:none" in css
    assert 'className="rankings-empty"' in source
    assert "No scores in this view yet." in source

def test_prelaunch_dates_are_not_player_visible_or_playable():
    from datetime import date
    from app.schedule import game_is_archive, game_is_in_archive, game_is_playable

    today = date(2026, 10, 7)
    for game_day in (date(2026, 9, 7), date(2026, 9, 14)):
        assert game_is_in_archive(game_day) is False
        assert game_is_playable(game_day, today=today) is False
        assert game_is_archive(game_day, today=today) is False

    assert game_is_in_archive(date(2026, 9, 21)) is True
    assert game_is_playable(date(2026, 9, 21), today=today) is True


def test_prelaunch_completion_is_rejected(app):
    import pytest

    profile_id = _profile(app, username="PrelaunchScorer")
    user_key = profile_user_key(profile_id)
    with app.app_context(), pytest.raises(ValueError, match="production scoring begins"):
        finalize_game_stats(user_key, "mystery", "2026-09-14", 100, True, competitive=False)

def test_mystery_leaderboard_includes_archive_points_and_metrics(app):
    from datetime import date
    from app.db import (
        finalize_game_stats,
        get_leaderboard,
        get_or_create_mystery_attempt,
        save_mystery_attempt,
    )

    profile_id = _profile(app, username="MysteryArchiveTester")
    user_key = profile_user_key(profile_id)

    games = [
        ("2026-09-21", 75, 2, False),
        ("2026-09-28", 100, 1, False),
        ("2026-10-05", 100, 1, True),
    ]

    with app.app_context():
        for game_date, score, clues, competitive in games:
            get_or_create_mystery_attempt(user_key, game_date)
            save_mystery_attempt(
                user_key,
                game_date,
                revealed_count=clues,
                guesses=[],
                completed=True,
                won=True,
                score=score,
            )
            finalize_game_stats(
                user_key,
                "mystery",
                game_date,
                score,
                True,
                competitive=competitive,
            )

        board = get_leaderboard(
            "all_time",
            "mystery",
            reference_day=date(2026, 10, 7),
            current_profile_id=profile_id,
        )

    assert board["me"]["points"] == 275
    assert board["me"]["detail"] == "3 solved · 1.3 avg clues"


def test_weekly_leaderboards_include_archive_earned_points(app):
    from datetime import date
    from app.db import get_home_leaderboard, get_weekly_leaderboard

    profile_id = _profile(app, username="WeeklyArchiveTester")
    user_key = profile_user_key(profile_id)

    with app.app_context():
        finalize_game_stats(
            user_key,
            "mystery",
            "2026-09-21",
            75,
            True,
            competitive=False,
        )

        weekly = get_weekly_leaderboard(date(2026, 9, 21))
        home = get_home_leaderboard(
            date(2026, 9, 21),
            current_profile_id=profile_id,
        )

    weekly_me = next(row for row in weekly if row["profile_id"] == profile_id)
    home_me = next(row for row in home if row["profile_id"] == profile_id)

    assert weekly_me["points"] == 75
    assert home_me["points"] == 75
    assert home_me["rank"] == 1

def test_today_mobile_layout_css_is_present_and_balanced():
    root = Path(__file__).parents[1]
    css = (root / "frontend" / "src" / "player" / "styles" / "home.css").read_text(
        encoding="utf-8"
    )

    assert css.count("{") == css.count("}")
    assert "@media (max-width:760px)" in css

    mobile = css.split("@media (max-width:760px)", 1)[1].split(
        "@media (max-width:390px)", 1
    )[0]

    assert ".v17-grid" in mobile
    assert "flex-direction:column" in mobile
    assert ".v17-day" in mobile
    assert ".v17-feature-card" in mobile
    assert 'grid-template-areas:' in mobile
    assert '"season season"' in mobile

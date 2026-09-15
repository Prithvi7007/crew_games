from pathlib import Path
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from app.db import (
    create_profile,
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
        finalize_game_stats(user_key, "word", "2026-09-09", 100, True, competitive=True)
        row = get_game_completion(user_key, "word", "2026-09-09")
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
                "2026-09-09",
                score,
                True,
                competitive=True,
            )
        rows = get_home_leaderboard(date(2026, 9, 9), current_profile_id=ids[3])

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
        session["user"] = {"profile_id": profile_id, "username": "SignoutTester", "avatar": "⭐", "user_key": profile_user_key(profile_id), "session_version": 1}
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'action="/logout"' in html
    assert ">Sign out<" in html



def test_global_account_menu_exposes_profile_and_sign_out():
    root = Path(__file__).parents[1]
    partial = (root / "app" / "templates" / "_account_menu.html").read_text(encoding="utf-8")
    assert 'data-account-trigger' in partial
    assert 'aria-haspopup="menu"' in partial
    assert 'href="{{ url_for(\'auth.profile\') }}"' in partial
    assert 'action="{{ url_for(\'auth.logout\') }}"' in partial
    assert '>Sign out<' in partial

    app_header = (root / "app" / "templates" / "_app_header.html").read_text(encoding="utf-8")
    assert '{% include "_account_menu.html" %}' in app_header

    for name in ["home.html", "games.html", "leaderboard.html", "profile.html", "mystery.html", "trivia.html", "tick_tock.html", "word.html"]:
        template = (root / "app" / "templates" / name).read_text(encoding="utf-8")
        assert '{% include "_app_header.html" %}' in template

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

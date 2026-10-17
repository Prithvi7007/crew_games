"""Optimistic publishing review invalidation for same-second edits."""

import re

from app.db import get_game_content, save_game_content
from tests.test_v2_access import _profile, _sign_in


def test_review_cannot_overwrite_a_newer_draft_even_with_same_timestamp(app, monkeypatch):
    import app.db as database

    monkeypatch.setattr(database, "_db_timestamp", lambda value=None: "2026-10-17T10:00:00")
    editor_id = _profile(app, "SameSecondEditor", "admin")
    client = app.test_client()
    csrf = _sign_in(client, app, editor_id)
    game_date = "2026-11-16"
    path = f"/admin/game/mystery/{game_date}"

    with app.app_context():
        save_game_content("mystery", game_date, "", {
            "answer": "FIRST", "accepted": ["FIRST"],
            "clues": ["a", "b", "c", "d"],
        }, status="draft")

    reviewed = client.post(path, data={
        "csrf_token": csrf, "action": "review",
        "answer": "SECOND", "accepted": "SECOND",
        "clue_1": "Screen", "clue_2": "Cast", "clue_3": "Film", "clue_4": "Movie",
    })
    assert reviewed.status_code == 200
    match = re.search(r'name="publish_token" value="([^"]+)"', reviewed.get_data(as_text=True))
    assert match

    with app.app_context():
        save_game_content("mystery", game_date, "", {
            "answer": "THIRD", "accepted": ["THIRD"],
            "clues": ["1", "2", "3", "4"],
        }, status="draft")

    blocked = client.post(path, data={
        "csrf_token": csrf, "action": "confirm_publish", "publish_token": match.group(1),
    })
    assert blocked.status_code == 200
    assert "no longer matches" in blocked.get_data(as_text=True)
    with app.app_context():
        row = get_game_content("mystery", game_date)
        assert row["status"] == "draft"
        assert row["content"]["answer"] == "THIRD"

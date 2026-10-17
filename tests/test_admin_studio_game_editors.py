"""Phase 2B Admin Studio game-editor usability and safe form compatibility."""

from pathlib import Path

import pytest

from app.db import get_game_content
from tests.test_v2_access import _profile, _sign_in


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "game,day,workspace,expected",
    [
        ("mystery", "2027-02-22", "studio-mystery-editor", "100 PTS"),
        ("word", "2027-02-24", "studio-word-editor", "SOLUTION PREVIEW"),
        ("tick_tock", "2027-02-25", "studio-timer-editor", "TARGET PREVIEW"),
    ],
)
def test_other_game_editors_have_accessible_previews_and_keep_original_fields(
    app, game, day, workspace, expected
):
    admin_id = _profile(app, f"StudioView{game}", "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)
    response = client.get(f"/admin/game/{game}/{day}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert workspace in html
    assert expected in html
    assert "v23-admin-game-editors.js" in html
    assert "v22-admin-studio.css" in html
    assert 'data-studio-status aria-live="polite"' in html
    assert 'name="csrf_token"' in html
    assert 'name="action" value="draft"' in html
    assert 'name="action" value="review"' in html
    assert "Confirm &amp; publish" not in html

    if game == "mystery":
        assert html.count('data-studio-clue="') == 4
        for number in range(1, 5):
            assert f'name="clue_{number}"' in html
        assert 'name="answer"' in html
        assert 'name="accepted"' in html
    elif game == "word":
        assert html.count('data-studio-tile="') == 5
        assert 'name="solution"' in html
        assert 'pattern="[A-Za-z]{5}"' in html
    else:
        assert 'name="target_seconds"' in html
        assert 'data-studio-timer-fill' in html


@pytest.mark.parametrize(
    "game,day,payload,expected",
    [
        ("mystery", "2027-03-01", {
            "answer": "STARDUST", "accepted": "STARDUST, STAR DUST",
            "clue_1": "A name on a poster", "clue_2": "A skyward hint",
            "clue_3": "A space-themed word", "clue_4": "Cosmic particles",
        }, ("answer", "STARDUST")),
        ("word", "2027-03-03", {"solution": "MOVIE"}, ("solution", "MOVIE")),
        ("tick_tock", "2027-03-04", {"target_seconds": "12.35"}, ("target_seconds", 12.35)),
    ],
)
def test_studio_enhancements_preserve_save_draft_contract(app, game, day, payload, expected):
    admin_id = _profile(app, f"StudioSave{game}", "admin")
    client = app.test_client()
    csrf = _sign_in(client, app, admin_id)
    response = client.post(
        f"/admin/game/{game}/{day}",
        data={"csrf_token": csrf, "action": "draft", "theme_label": "", **payload},
    )
    assert response.status_code == 302
    with app.app_context():
        saved = get_game_content(game, day)
        assert saved["status"] == "draft"
        assert saved["content"][expected[0]] == expected[1]


def test_client_previews_are_advisory_and_do_not_intercept_publishing():
    js = (ROOT / "app/static/js/v23-admin-game-editors.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/css/v22-admin-studio.css").read_text(encoding="utf-8")
    page = (ROOT / "app/templates/admin/editor.html").read_text(encoding="utf-8")

    assert "This clue contains the answer" in js
    assert "This clue repeats an earlier clue" in js
    assert "^[A-Za-z]{5}$" in js
    assert "seconds >= 2 && seconds <= 30" in js
    assert "querySelector('[data-studio-editor]')" in js
    assert "fetch(" not in js
    assert ".submit(" not in js
    assert "preventDefault(" not in js
    assert "[data-studio-locked" not in js
    assert ".studio-clue-timeline" in css
    assert ".studio-word-editor" not in css or ".studio-word-layout" in css
    assert ".studio-timer-visual" in css
    assert 'action" value="review"' in page

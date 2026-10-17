"""Admin Studio schedule/editor UX contracts (no production or account writes)."""

from pathlib import Path

from app.db import save_game_content
from tests.test_v2_access import _profile, _sign_in


ROOT = Path(__file__).resolve().parents[1]


def test_schedule_readiness_displays_actual_published_draft_and_fallback_counts(app):
    actor_id = _profile(app, "CalendarStudioAdmin", "admin")
    client = app.test_client()
    _sign_in(client, app, actor_id)
    monday = "2027-02-22"

    with app.app_context():
        save_game_content("mystery", monday, "Film night", {
            "answer": "CINEMA",
            "accepted": ["CINEMA"],
            "clues": ["Screen", "Tickets", "Popcorn", "Movie"],
        }, status="published")
        save_game_content("trivia", "2027-02-23", "", {
            "questions": [{
                "prompt": f"Movie question {number}?",
                "options": ["A", "B", "C", "D"],
                "answer": 0,
            } for number in range(1, 11)],
        }, status="draft")

    response = client.get(f"/admin?week={monday}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert '<progress class="studio-readiness-progress" value="1" max="4"' in html
    assert "CUSTOM CONTENT READINESS" in html
    assert "Back to this week" in html
    assert html.count('class="glass-card admin-game-card studio-schedule-card') == 4
    assert "Saved draft · players use fallback" in html
    assert "Built-in fallback is playable" in html
    assert "Custom content is live" in html
    assert "Locked after play" in html
    assert "v22-admin-studio.css" in html


def test_trivia_editor_has_all_navigable_questions_without_hiding_native_fields(app):
    actor_id = _profile(app, "TriviaStudioAdmin", "admin")
    client = app.test_client()
    _sign_in(client, app, actor_id)
    response = client.get("/admin/game/trivia/2027-02-23")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'aria-label="Trivia question navigator"' in html
    assert html.count('class="studio-question-jump"') == 10
    assert html.count('class="admin-question-card" id="studio-question-') == 10
    assert html.count('class="studio-question-note" data-studio-question-note') == 10
    assert 'data-studio-ready-count aria-live="polite"' in html
    assert 'name="q10_prompt"' in html
    assert 'name="q10_d"' in html
    assert 'value="review"' in html
    assert 'value="draft"' in html
    assert 'v22-admin-editor.js' in html
    assert 'v22-admin-studio.css' in html
    assert "Confirm &amp; publish" not in html


def test_studio_editor_is_progressive_and_does_not_modify_publishing_endpoints():
    source = (ROOT / "app/static/js/v22-admin-editor.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/css/v22-admin-studio.css").read_text(encoding="utf-8")
    editor = (ROOT / "app/templates/admin/editor.html").read_text(encoding="utf-8")

    assert "querySelectorAll('[data-studio-question]')" in source
    assert "Duplicate" not in source  # warnings are advisory, not new backend validation
    assert "Possible duplicate answer choices." in source
    assert "This question appears more than once" in source
    assert "requestAnimationFrame" in source
    assert "fetch(" not in source
    assert "form.submit(" not in source
    assert ".studio-trivia-questions .admin-question-card { display: none" not in css
    assert 'tabindex="-1"' in editor

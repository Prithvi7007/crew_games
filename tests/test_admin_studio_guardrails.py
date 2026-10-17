"""Authorization and publishing review contracts for Admin Studio."""

import re

import pytest

from app.db import get_game_content, get_profile_by_id, save_game_content
from tests.test_v2_access import _breakglass, _profile, _sign_in


def _puzzle_form(csrf_token, action="review", answer="CINEMA"):
    return {
        "csrf_token": csrf_token,
        "action": action,
        "theme_label": "Movie night",
        "answer": answer,
        "accepted": answer,
        "clue_1": "Screen",
        "clue_2": "Popcorn",
        "clue_3": "Tickets",
        "clue_4": "Movie theater",
    }


def _review_token(response):
    body = response.get_data(as_text=True)
    assert "FINAL PUBLICATION CHECK" in body
    assert "Confirm &amp; publish" in body
    match = re.search(r'name="publish_token" value="([^"]+)"', body)
    assert match
    return match.group(1)


@pytest.mark.parametrize("target_role", ["admin", "owner"])
@pytest.mark.parametrize("operation", ["reset-password", "reset-recovery", "force-sign-out"])
def test_standard_admin_cannot_change_privileged_credentials_or_sessions(
    app, target_role, operation
):
    admin_id = _profile(app, f"StandardManager{target_role}{operation}", "admin")
    target_id = _profile(app, f"PrivilegedTarget{target_role}{operation}", target_role)
    client = app.test_client()
    csrf = _sign_in(client, app, admin_id)
    with app.app_context():
        before = dict(get_profile_by_id(target_id))

    detail = client.get(f"/admin/players/{target_id}").get_data(as_text=True)
    assert "Restricted credentials" in detail
    assert "Generate temporary password" not in detail

    response = client.post(
        f"/admin/players/{target_id}/{operation}", data={"csrf_token": csrf}
    )
    assert response.status_code == 302
    with app.app_context():
        after = dict(get_profile_by_id(target_id))
    for field in ("password_hash", "recovery_code_hash", "session_version", "role"):
        assert after[field] == before[field]


def test_admin_cannot_demote_another_admin_to_bypass_credential_protection(app):
    admin_id = _profile(app, "ManagerCannotDemote", "admin")
    target_id = _profile(app, "PrivilegedCannotDemote", "admin")
    client = app.test_client()
    csrf = _sign_in(client, app, admin_id)
    response = client.post(
        f"/admin/players/{target_id}/role",
        data={"csrf_token": csrf, "role": "player"},
    )
    assert response.status_code == 302
    with app.app_context():
        assert get_profile_by_id(target_id)["role"] == "admin"


def test_owner_profile_can_manage_admin_but_only_breakglass_can_manage_owner(app):
    owner_id = _profile(app, "AuthenticatedOwner", "owner")
    peer_admin_id = _profile(app, "OtherAdministrator", "admin")
    other_owner_id = _profile(app, "ProtectedOwner", "owner")
    client = app.test_client()
    csrf = _sign_in(client, app, owner_id)
    allowed = client.post(
        f"/admin/players/{peer_admin_id}/reset-password", data={"csrf_token": csrf}
    )
    assert allowed.status_code == 200
    assert "Temporary password" in allowed.get_data(as_text=True)
    denied = client.post(
        f"/admin/players/{other_owner_id}/reset-recovery", data={"csrf_token": csrf}
    )
    assert denied.status_code == 302

    breakglass_client = app.test_client()
    admin_token = _breakglass(breakglass_client)
    allowed_owner = breakglass_client.post(
        f"/admin/players/{other_owner_id}/reset-recovery",
        data={"csrf_token": admin_token},
    )
    assert allowed_owner.status_code == 200
    assert "New recovery code" in allowed_owner.get_data(as_text=True)


def test_publish_requires_explicit_signed_review_and_does_not_mutate_until_confirmed(app):
    admin_id = _profile(app, "PublicationReviewer", "admin")
    client = app.test_client()
    csrf = _sign_in(client, app, admin_id)
    path = "/admin/game/mystery/2026-10-26"

    direct = client.post(path, data=_puzzle_form(csrf, "publish"))
    assert direct.status_code == 200
    with app.app_context():
        assert get_game_content("mystery", "2026-10-26") is None

    review = client.post(path, data=_puzzle_form(csrf))
    assert review.status_code == 200
    token = _review_token(review)
    assert "CINEMA" in review.get_data(as_text=True)
    with app.app_context():
        assert get_game_content("mystery", "2026-10-26") is None

    invalid = client.post(
        path, data={"csrf_token": csrf, "action": "confirm_publish", "publish_token": "forged"}
    )
    assert invalid.status_code == 200

    published = client.post(
        path, data={"csrf_token": csrf, "action": "confirm_publish", "publish_token": token}
    )
    assert published.status_code == 302
    with app.app_context():
        saved = get_game_content("mystery", "2026-10-26")
        assert saved["status"] == "published"
        assert saved["content"]["answer"] == "CINEMA"


def test_review_does_not_temporarily_unpublish_existing_game(app):
    admin_id = _profile(app, "UpdateReviewer", "admin")
    client = app.test_client()
    csrf = _sign_in(client, app, admin_id)
    path = "/admin/game/mystery/2026-11-02"
    with app.app_context():
        save_game_content("mystery", "2026-11-02", "", {
            "answer": "ORIGINAL", "accepted": ["ORIGINAL"],
            "clues": ["a", "b", "c", "d"],
        }, status="published")
    response = client.post(path, data=_puzzle_form(csrf, answer="UPDATED"))
    assert response.status_code == 200
    token = _review_token(response)
    with app.app_context():
        saved = get_game_content("mystery", "2026-11-02")
        assert saved["status"] == "published"
        assert saved["content"]["answer"] == "ORIGINAL"

    client.post(path, data={"csrf_token": csrf, "action": "confirm_publish", "publish_token": token})
    with app.app_context():
        assert get_game_content("mystery", "2026-11-02")["content"]["answer"] == "UPDATED"


def test_publish_review_is_bound_to_the_actor_and_current_saved_content(app):
    first = _profile(app, "FirstReviewer", "admin")
    second = _profile(app, "SecondReviewer", "admin")
    client = app.test_client()
    csrf = _sign_in(client, app, first)
    path = "/admin/game/mystery/2026-11-09"
    reviewed = client.post(path, data=_puzzle_form(csrf))
    token = _review_token(reviewed)

    other = app.test_client()
    other_csrf = _sign_in(other, app, second)
    denied = other.post(
        path, data={"csrf_token": other_csrf, "action": "confirm_publish", "publish_token": token}
    )
    assert denied.status_code == 200
    with app.app_context():
        assert get_game_content("mystery", "2026-11-09") is None

    # A concurrent change makes even a previously signed review stale.
    with app.app_context():
        save_game_content("mystery", "2026-11-09", "", {
            "answer": "EXISTING", "accepted": ["EXISTING"],
            "clues": ["a", "b", "c", "d"],
        }, status="draft")
    denied = client.post(
        path, data={"csrf_token": csrf, "action": "confirm_publish", "publish_token": token}
    )
    assert denied.status_code == 200
    with app.app_context():
        saved = get_game_content("mystery", "2026-11-09")
        assert saved["status"] == "draft"
        assert saved["content"]["answer"] == "EXISTING"

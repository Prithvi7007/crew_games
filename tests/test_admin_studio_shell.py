"""Shared Admin Studio navigation must be consistent and safe across operations."""

from datetime import date
from pathlib import Path

import pytest

from app.db import get_season_for_date
from tests.test_v2_access import _profile, _sign_in


ADMIN_TEMPLATES = (
    "dashboard.html", "editor.html", "players.html", "player_detail.html",
    "settings.html", "championships.html", "preview.html",
    "publish_review.html", "test_game.html",
)


@pytest.mark.parametrize("route,section", [
    ("/admin", "Schedule"),
    ("/admin/players", "Players"),
    ("/admin/settings", "Settings"),
    ("/admin/game/mystery/2027-02-22", "Schedule"),
    ("/admin/preview/mystery/2027-02-22", "Schedule"),
    ("/admin/test/mystery/2027-02-22", "Schedule"),
])
def test_studio_routes_share_a_consistent_active_navigation(app, route, section):
    admin_id = _profile(app, "StudioShell" + section + str(len(route)), "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)
    response = client.get(route)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('aria-label="CREW Admin Studio home"') == 1
    assert html.count('aria-label="Studio sections"') == 1
    assert html.count('aria-label="Admin Studio sections"') == 1
    assert html.count('aria-current="page"') == 2
    assert 'href="/admin/settings#studio-seasons"' in html
    assert 'href="/admin/settings#studio-access"' in html
    assert 'href="/home"' in html
    assert 'action="/admin/logout"' in html
    assert 'name="csrf_token"' in html
    assert "v24-admin-shell.css" in html
    assert f'aria-current="page" href="/admin' in html or section == "Players"

    if route == "/admin/settings":
        assert 'id="studio-seasons"' in html
        assert 'id="studio-access"' in html
    if route == "/admin/game/mystery/2027-02-22":
        assert "Back to weekly schedule" in html
    if route.startswith("/admin/preview/") or route.startswith("/admin/test/"):
        assert "Back to editor" in html


def test_championship_review_uses_seasons_section_not_settings(app):
    admin_id = _profile(app, "StudioChampionshipNav", "admin")
    client = app.test_client()
    _sign_in(client, app, admin_id)
    with app.app_context():
        season_id = get_season_for_date(date(2026, 10, 20))["id"]
    response = client.get(f"/admin/seasons/{season_id}/championships")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="active" aria-current="page" href="/admin/settings#studio-seasons"' in html
    assert "All seasons" in html
    assert html.count('aria-current="page"') == 2


def test_admin_studio_includes_one_shared_header_per_page():
    root = Path(__file__).resolve().parents[1] / "app" / "templates" / "admin"
    for filename in ADMIN_TEMPLATES:
        text = (root / filename).read_text(encoding="utf-8")
        assert text.count('{% include "admin/_studio_header.html" %}') == 1, filename
        assert '{% include "admin/_mobile_nav.html" %}' not in text, filename
        assert "v24-admin-shell.css" in text, filename

    header = (root / "_studio_header.html").read_text(encoding="utf-8")
    assert header.count('{% include "admin/_mobile_nav.html" %}') == 1
    assert 'method="post" action="{{ url_for(\'admin.logout\') }}"' in header
    assert 'name="csrf_token"' in header
    assert "studio-shell-context-action" in header


def test_studio_navigation_never_exposes_privileged_mutation_links():
    root = Path(__file__).resolve().parents[1] / "app" / "templates" / "admin"
    navigation = (root / "_studio_header.html").read_text(encoding="utf-8")
    navigation += (root / "_mobile_nav.html").read_text(encoding="utf-8")
    assert "url_for('admin.player_reset_password')" not in navigation
    assert "url_for('admin.player_role')" not in navigation
    assert 'admin.review_championships' in navigation
    assert 'admin.logout' in navigation

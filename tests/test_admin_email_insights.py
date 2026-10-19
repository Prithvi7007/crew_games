"""Admin newsletter status must be accurate, read-only and private."""

import json
from datetime import date
from unittest.mock import patch

from app.admin.email_insights import weekly_delivery_insights
from app.db import get_setting, set_setting
from tests.test_v2_access import _profile, _sign_in


def test_handoffs_distinguish_provider_acceptance_from_missing_receipts(app):
    with app.app_context():
        set_setting("email.weekly_kickoff.enabled", "1")
        set_setting("email.weekly_kickoff.to", "team@example.com,staff@example.com")
        set_setting("email.weekly_kickoff.2026-10-12", json.dumps({
            "resend_id": "email_123", "week_start": "2026-10-12",
            "subject": "CREW Games Weekly", "to": ["team@example.com"],
        }))
        with patch.dict(app.config, {"RESEND_API_KEY": "test-provider-token", "CREW_EMAIL_FROM": "crew@example.com"}):
            summary = weekly_delivery_insights(date(2026, 10, 19))
        assert summary["state"] == "not_recorded"
        assert summary["recipient_count"] == 2
        assert summary["history"][0]["accepted"] is False
        assert summary["history"][1]["accepted"] is True
        assert summary["history"][1]["recipient_count"] == 1


def test_invalid_receipts_cannot_be_shown_as_success(app):
    with app.app_context():
        set_setting("email.weekly_kickoff.2026-10-19", '{bad json')
        assert weekly_delivery_insights(date(2026, 10, 19))["history"][0]["accepted"] is False
        set_setting("email.weekly_kickoff.2026-10-19", json.dumps({"resend_id": "any", "week_start": "2026-10-12"}))
        assert weekly_delivery_insights(date(2026, 10, 19))["history"][0]["accepted"] is False


def test_disabled_email_and_missing_sender_have_clear_diagnostic_states(app):
    with app.app_context():
        set_setting("email.weekly_kickoff.enabled", "0")
        paused = weekly_delivery_insights(date(2026, 10, 19))
        assert paused["state"] == "paused"
        set_setting("email.weekly_kickoff.enabled", "1")
        set_setting("email.weekly_kickoff.to", "team@example.com")
        with patch.dict(app.config, {"RESEND_API_KEY": "", "CREW_EMAIL_FROM": ""}):
            missing = weekly_delivery_insights(date(2026, 10, 19))
        assert missing["state"] == "setup_needed"
        assert "Resend API key" in missing["missing"]


def test_history_stops_at_crew_launch_and_is_bounded(app):
    with app.app_context():
        summary = weekly_delivery_insights(date(2026, 9, 21), weeks=100)
    assert [x["week_start"] for x in summary["history"]] == [date(2026, 9, 21)]


def test_status_is_admin_only_and_does_not_modify_saved_settings(app):
    admin_id = _profile(app, "WeeklyStatusAdmin", "admin")
    player_id = _profile(app, "WeeklyStatusPlayer")
    with app.app_context():
        set_setting("email.weekly_kickoff.2026-10-19", json.dumps({
            "resend_id": "email_valid", "week_start": "2026-10-19", "to": ["team@example.com"],
        }))
        before = get_setting("email.weekly_kickoff.2026-10-19")

    admin_client = app.test_client()
    _sign_in(admin_client, app, admin_id)
    with patch("app.admin.routes.crew_today", return_value=date(2026, 10, 19)):
        response = admin_client.get("/admin/settings")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Monday newsletter status" in html
    assert "Accepted by Resend" in html
    assert "not that the message reached an inbox" in html
    assert "email_valid" not in html
    assert "v26-admin-email-insights.css" in html

    player_client = app.test_client()
    _sign_in(player_client, app, player_id)
    assert player_client.get("/admin/settings").status_code == 302
    with app.app_context():
        assert get_setting("email.weekly_kickoff.2026-10-19") == before

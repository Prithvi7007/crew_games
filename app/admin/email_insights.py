"""Read-only weekly newsletter diagnostics for authenticated Admin Studio pages."""

import json
from datetime import timedelta

from flask import current_app

from app.db import get_setting
from app.schedule import CREW_WEEK_ONE_DATE, crew_today, get_week_start
from app.weekly_email import _weekly_email_recipients


def weekly_delivery_insights(reference_day=None, weeks=6):
    """Summarize Resend handoff receipts, never infer inbox delivery.

    A missing receipt is NOT proof a scheduled send failed. This view does
    not contact Resend, inspect host timers, or mutate application state.
    """
    reference_day = reference_day or crew_today()
    current_monday = get_week_start(reference_day)
    enabled_raw = get_setting("email.weekly_kickoff.enabled")
    enabled = enabled_raw is None or str(enabled_raw).strip().lower() in {"1", "true", "yes", "on"}
    recipient_count = len(_weekly_email_recipients())
    api_configured = bool(str(current_app.config.get("RESEND_API_KEY") or "").strip())
    sender_configured = bool(str(current_app.config.get("CREW_EMAIL_FROM") or "").strip())

    history = []
    for index in range(min(max(int(weeks), 1), 12)):
        monday = current_monday - timedelta(weeks=index)
        if monday < CREW_WEEK_ONE_DATE:
            break
        raw_receipt = get_setting(f"email.weekly_kickoff.{monday.isoformat()}")
        receipt = None
        if raw_receipt:
            try:
                decoded = json.loads(raw_receipt)
            except (ValueError, TypeError):
                decoded = None
            if isinstance(decoded, dict) and decoded.get("resend_id") and decoded.get("week_start", monday.isoformat()) == monday.isoformat():
                receipt = decoded
        history.append({
            "week_start": monday,
            "accepted": receipt is not None,
            "recipient_count": len(receipt.get("to")) if receipt and isinstance(receipt.get("to"), list) else None,
            "is_current": index == 0,
        })

    missing = []
    if recipient_count == 0:
        missing.append("recipient list")
    if not sender_configured:
        missing.append("sender address")
    if not api_configured:
        missing.append("Resend API key")

    if not enabled:
        state = "paused"
    elif missing:
        state = "setup_needed"
    elif history and history[0]["accepted"]:
        state = "accepted"
    else:
        state = "not_recorded"

    return {
        "state": state,
        "enabled": enabled,
        "missing": missing,
        "recipient_count": recipient_count,
        "provider_configured": api_configured and sender_configured,
        "history": history,
    }

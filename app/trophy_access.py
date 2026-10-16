"""Server-controlled public badge availability, opened October 16, 2026.

Saved seasonal awards remain authoritative. Admin/owner visual previews
continue to work independently of the public reveal date.
"""
from datetime import date

from app.schedule import crew_today

TROPHY_PUBLIC_REVEAL_DATE = date(2026, 10, 16)


def trophy_preview_enabled(user):
    """Admins and owners may try all badges without earning or persisting awards."""
    return (user or {}).get("role") in ("admin", "owner")


def trophies_visible_to(user, today=None):
    if trophy_preview_enabled(user):
        return True
    day = today if today is not None else crew_today()
    return day >= TROPHY_PUBLIC_REVEAL_DATE

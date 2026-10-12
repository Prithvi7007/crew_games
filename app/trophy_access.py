"""Temporary public trophy-room hold for the October 12-18 CREW week.

Players keep earning badges in the database while the collection is hidden.
It becomes visible automatically on Monday, October 19 in CREW's timezone.
Owner/admin accounts retain preview access.
"""
from datetime import date

from app.schedule import crew_today

TROPHY_PUBLIC_REVEAL_DATE = date(2026, 10, 19)


def trophy_preview_enabled(user):
    """Admins and owners may try all badges without earning or persisting awards."""
    return (user or {}).get("role") in ("admin", "owner")


def trophies_visible_to(user, today=None):
    if trophy_preview_enabled(user):
        return True
    day = today if today is not None else crew_today()
    return day >= TROPHY_PUBLIC_REVEAL_DATE

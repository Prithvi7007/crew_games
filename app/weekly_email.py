import json
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import click
from flask import current_app

from app.db import get_competitive_rankings_between, get_setting, set_setting
from app.schedule import (
    CREW_WEEK_ONE_DATE,
    GAME_DEFINITIONS,
    crew_today,
    get_crew_week_number,
    get_week_start,
)

RESEND_EMAILS_URL = "https://api.resend.com/emails"

GAME_EMAIL_META = {
    "mystery": {"icon": "?", "path": "/mystery"},
    "trivia": {"icon": "✦", "path": "/trivia"},
    "word": {"icon": "W", "path": "/word"},
    "tick_tock": {"icon": "◷", "path": "/tick-tock"},
}


def _week_number_label(number):
    return f"{int(number):02d}"


def _week_range_label(monday):
    thursday = monday + timedelta(days=3)
    if monday.month == thursday.month:
        return f"{monday.strftime('%b')} {monday.day}–{thursday.day}, {monday.year}"
    return f"{monday.strftime('%b %d')}–{thursday.strftime('%b %d')}, {monday.year}"


def _long_date_label(day):
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def _recipients(raw):
    return [value.strip() for value in str(raw or "").replace(";", ",").split(",") if value.strip()]


def _weekly_email_enabled():
    raw = get_setting("email.weekly_kickoff.enabled")
    if raw is None:
        return True
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _weekly_email_recipients():
    admin_value = get_setting("email.weekly_kickoff.to")
    raw = admin_value if admin_value is not None else current_app.config.get("CREW_WEEKLY_EMAIL_TO", "")
    return _recipients(raw)


def build_weekly_kickoff_context(reference_day=None):
    """Build a frozen Monday recap through the previous CREW Thursday."""
    reference_day = reference_day or crew_today()
    current_week_start = get_week_start(reference_day)
    previous_week_start = current_week_start - timedelta(days=7)
    previous_week_end = previous_week_start + timedelta(days=3)

    current_week_number = get_crew_week_number(current_week_start)
    previous_week_number = get_crew_week_number(previous_week_start)

    previous_leaders = []
    season_leaders = []
    if previous_week_number > 0:
        previous_leaders = get_competitive_rankings_between(
            previous_week_start, previous_week_end, limit=10
        )
        season_leaders = get_competitive_rankings_between(
            CREW_WEEK_ONE_DATE, previous_week_end, limit=10
        )

    public_url = current_app.config.get("CREW_PUBLIC_URL", "https://cadacrew.fun").rstrip("/")
    games = []
    for definition in GAME_DEFINITIONS:
        game_date = current_week_start + timedelta(days=definition["weekday"])
        meta = GAME_EMAIL_META[definition["key"]]
        games.append({
            "key": definition["key"],
            "day": definition["day"],
            "date_label": f"{game_date.strftime('%b')} {game_date.day}",
            "title": definition["title"],
            "points": int(definition["points"]),
            "icon": meta["icon"],
            "url": public_url + meta["path"],
            "status": "Available now" if game_date <= reference_day else f"Available {definition['day']}",
        })

    podium = []
    for index in (1, 0, 2):
        if index < len(previous_leaders):
            player = dict(previous_leaders[index])
            player["podium_rank"] = index + 1
            podium.append(player)

    return {
        "reference_day": reference_day,
        "reference_date_label": _long_date_label(reference_day),
        "current_week_start": current_week_start,
        "previous_week_start": previous_week_start,
        "previous_week_end": previous_week_end,
        "current_week_number": current_week_number,
        "current_week_number_label": _week_number_label(current_week_number),
        "previous_week_number": previous_week_number,
        "previous_week_number_label": _week_number_label(previous_week_number),
        "previous_week_range": _week_range_label(previous_week_start),
        "previous_leaders": previous_leaders,
        "previous_rows": previous_leaders[3:],
        "podium": podium,
        "season_leaders": season_leaders,
        "games": games,
        "play_url": public_url + "/games",
        "leaderboard_url": public_url + "/leaderboard",
        "public_url": public_url,
    }


def _subject(context):
    return f"CREW Games Weekly | Week {context['current_week_number_label']} is Live"


def _plain_text(context):
    lines = [
        "CREW GAMES WEEKLY",
        context["reference_date_label"],
        "",
        f"Week {context['current_week_number_label']} is Live",
        f"Week {context['previous_week_number_label']} results, cumulative standings, and this week's games.",
        "",
        f"WEEK {context['previous_week_number_label']} FINAL STANDINGS",
        context["previous_week_range"],
    ]

    if context["previous_leaders"]:
        for player in context["previous_leaders"]:
            lines.append(f"{player['rank']}. {player['username']} — {player['points']} pts")
    else:
        lines.append("No competitive scores were recorded.")

    lines.extend(["", f"CUMULATIVE STANDINGS — THROUGH WEEK {context['previous_week_number_label']}"])
    if context["season_leaders"]:
        for player in context["season_leaders"]:
            lines.append(f"{player['rank']}. {player['username']} — {player['points']} pts")
    else:
        lines.append("No cumulative scores yet.")

    lines.extend(["", f"WEEK {context['current_week_number_label']} GAMES", "Four games. Up to 400 points available."])
    for game in context["games"]:
        lines.append(f"{game['day']} · {game['title']} · {game['status']} · up to {game['points']} pts")

    lines.extend(["", f"Open CREW Games: {context['play_url']}", f"View full leaderboard: {context['leaderboard_url']}"])
    return "\n".join(lines)


def render_weekly_kickoff(reference_day=None):
    context = build_weekly_kickoff_context(reference_day)
    if context["previous_week_number"] < 1:
        return {
            "status": "skipped",
            "reason": "There is no completed CREW week to recap yet.",
            "context": context,
        }

    return {
        "status": "ready",
        "subject": _subject(context),
        "html": current_app.jinja_env.get_template("emails/weekly_kickoff.html").render(**context),
        "text": _plain_text(context),
        "context": context,
    }


def _send_with_resend(subject, html_body, text_body, recipients, send_key):
    api_key = current_app.config.get("RESEND_API_KEY", "").strip()
    sender = current_app.config.get("CREW_EMAIL_FROM", "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured.")
    if not sender:
        raise RuntimeError("CREW_EMAIL_FROM is not configured.")
    if not recipients:
        raise RuntimeError("CREW_WEEKLY_EMAIL_TO is not configured.")

    payload = json.dumps({
        "from": sender,
        "to": recipients,
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }, ensure_ascii=False).encode("utf-8")

    request = Request(
        RESEND_EMAILS_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "CREW-Weekly-Kickoff/1.0",
            "Idempotency-Key": send_key,
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Resend returned HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Resend: {exc.reason}") from exc

    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Resend returned an invalid JSON response.") from exc

    if not result.get("id"):
        raise RuntimeError(f"Resend did not return an email id: {result}")
    return result


def send_weekly_kickoff(reference_day=None, force=False, dry_run=False):
    if not _weekly_email_enabled():
        return {
            "status": "disabled",
            "reason": "Weekly CREW email is disabled in Admin Studio.",
        }

    rendered = render_weekly_kickoff(reference_day)
    if rendered["status"] != "ready":
        return rendered

    context = rendered["context"]
    send_key = f"crew-weekly-kickoff-{context['current_week_start'].isoformat()}"
    setting_key = f"email.weekly_kickoff.{context['current_week_start'].isoformat()}"

    if force:
        send_key = f"{send_key}-force-{uuid4().hex[:12]}"

    if get_setting(setting_key) and not force:
        return {
            "status": "already_sent",
            "reason": "This week's Monday kickoff email was already sent.",
            "send_key": send_key,
            "subject": rendered["subject"],
            "context": context,
        }

    recipients = _weekly_email_recipients()
    if not recipients:
        raise RuntimeError(
            "Weekly email recipient is not configured in Admin Studio or CREW_WEEKLY_EMAIL_TO."
        )

    if dry_run:
        return {**rendered, "status": "dry_run", "recipients": recipients, "send_key": send_key}

    result = _send_with_resend(rendered["subject"], rendered["html"], rendered["text"], recipients, send_key)
    receipt = {
        "resend_id": result["id"],
        "subject": rendered["subject"],
        "to": recipients,
        "week_start": context["current_week_start"].isoformat(),
    }
    set_setting(setting_key, json.dumps(receipt, ensure_ascii=False))
    current_app.logger.info(
        "Weekly CREW kickoff email sent",
        extra={"resend_id": result["id"], "week_start": context["current_week_start"].isoformat()},
    )
    return {
        "status": "sent",
        "resend_id": result["id"],
        "recipients": recipients,
        "subject": rendered["subject"],
        "context": context,
    }


def init_app(app):
    @app.cli.command("send-weekly-kickoff")
    @click.option("--force", is_flag=True, help="Send even if this CREW week is already marked sent.")
    @click.option("--dry-run", is_flag=True, help="Render and validate without contacting Resend.")
    @click.option(
        "--date",
        "raw_date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Optional reference date for testing. Defaults to the current CREW date.",
    )
    def send_weekly_kickoff_command(force, dry_run, raw_date):
        """Send the Monday recap + new-week kickoff email."""
        reference_day = None
        if raw_date:
            try:
                reference_day = date.fromisoformat(raw_date)
            except ValueError as exc:
                raise click.ClickException("--date must use YYYY-MM-DD.") from exc

        try:
            result = send_weekly_kickoff(reference_day=reference_day, force=force, dry_run=dry_run)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

        if result["status"] == "sent":
            click.echo(
                f"Sent {result['subject']} to {', '.join(result['recipients'])} "
                f"(Resend id {result['resend_id']})."
            )
        elif result["status"] == "dry_run":
            context = result["context"]
            click.echo(f"DRY RUN: {result['subject']}")
            click.echo(f"Recipients: {', '.join(result['recipients'])}")
            click.echo(
                f"Previous week leaders: {len(context['previous_leaders'])}; "
                f"season leaders: {len(context['season_leaders'])}."
            )
        else:
            click.echo(result.get("reason", result["status"]))

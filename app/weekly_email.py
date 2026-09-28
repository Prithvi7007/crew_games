import json
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


def _recipients(raw):
    return [value.strip() for value in str(raw or "").replace(";", ",").split(",") if value.strip()]


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
            "title": definition["title"],
            "points": int(definition["points"]),
            "icon": meta["icon"],
            "url": public_url + meta["path"],
            "status": "Available now" if game_date <= reference_day else f"Opens {definition['day']}",
        })

    podium = []
    for index in (1, 0, 2):
        if index < len(previous_leaders):
            player = dict(previous_leaders[index])
            player["podium_rank"] = index + 1
            podium.append(player)

    return {
        "reference_day": reference_day,
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
    return (
        f"🏆 CREW Week {context['previous_week_number_label']} Results — "
        f"Week {context['current_week_number_label']} Is Open"
    )


def _plain_text(context):
    lines = [
        "CREW GAMES — MONDAY KICKOFF",
        "",
        f"WEEK {context['previous_week_number_label']} RESULTS — WEEK {context['current_week_number_label']} IS OPEN",
        f"Previous week: {context['previous_week_range']}",
        "",
        f"WEEK {context['previous_week_number_label']} FINAL STANDINGS",
    ]

    if context["previous_leaders"]:
        for player in context["previous_leaders"]:
            lines.append(f"{player['rank']}. {player['username']} — {player['points']} pts")
    else:
        lines.append("No competitive scores were recorded.")

    lines.extend(["", f"SEASON LEADERBOARD — THROUGH WEEK {context['previous_week_number_label']}"])
    if context["season_leaders"]:
        for player in context["season_leaders"]:
            lines.append(f"{player['rank']}. {player['username']} — {player['points']} pts")
    else:
        lines.append("No season scores yet.")

    lines.extend([
        "",
        f"WEEK {context['current_week_number_label']} STARTS NOW",
        "A fresh leaderboard. 400 points up for grabs.",
    ])
    for game in context["games"]:
        lines.append(f"{game['title']} — {game['status']} — up to {game['points']} pts")

    lines.extend([
        "",
        f"Play this week: {context['play_url']}",
        f"View full leaderboard: {context['leaderboard_url']}",
    ])
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
    rendered = render_weekly_kickoff(reference_day)
    if rendered["status"] != "ready":
        return rendered

    context = rendered["context"]
    send_key = f"crew-weekly-kickoff-{context['current_week_start'].isoformat()}"
    setting_key = f"email.weekly_kickoff.{context['current_week_start'].isoformat()}"

    if get_setting(setting_key) and not force:
        return {
            "status": "already_sent",
            "reason": "This week's Monday kickoff email was already sent.",
            "send_key": send_key,
            "subject": rendered["subject"],
            "context": context,
        }

    recipients = _recipients(current_app.config.get("CREW_WEEKLY_EMAIL_TO", ""))
    if not recipients:
        raise RuntimeError("CREW_WEEKLY_EMAIL_TO is not configured.")

    if dry_run:
        return {**rendered, "status": "dry_run", "recipients": recipients, "send_key": send_key}

    result = _send_with_resend(
        rendered["subject"], rendered["html"], rendered["text"], recipients, send_key
    )
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

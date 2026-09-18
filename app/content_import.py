import json
from datetime import date
from pathlib import Path

import click

from app.db import count_game_attempts, get_game_content, save_game_content
from app.schedule import get_game_definition


BANK_PATH = Path(__file__).with_name("content") / "crew_question_bank.json"


def _load_bank():
    with BANK_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise click.ClickException("Question bank file is invalid.")
    return payload


def _validate_entry(entry):
    game_key = str(entry.get("game_key") or "")
    game_date = str(entry.get("game_date") or "")
    theme_label = str(entry.get("theme_label") or "")
    content = entry.get("content") or {}

    if game_key not in {"mystery", "trivia"}:
        raise click.ClickException(f"Unsupported question-bank game key: {game_key!r}")

    try:
        game_day = date.fromisoformat(game_date)
    except ValueError as exc:
        raise click.ClickException(f"Invalid game date: {game_date!r}") from exc

    definition = get_game_definition(game_key)
    if game_day.weekday() != definition["weekday"]:
        raise click.ClickException(
            f"{game_key} content is scheduled on the wrong weekday: {game_date}"
        )

    if game_key == "mystery":
        clues = content.get("clues") or []
        answer = str(content.get("answer") or "").strip()
        accepted = content.get("accepted") or []
        if len(clues) != 4 or any(not str(clue).strip() for clue in clues):
            raise click.ClickException(
                f"Mystery {game_date} must contain exactly four non-empty clues."
            )
        if not answer or not accepted:
            raise click.ClickException(
                f"Mystery {game_date} must contain an answer and accepted answers."
            )

    if game_key == "trivia":
        questions = content.get("questions") or []
        if len(questions) != 10:
            raise click.ClickException(
                f"Trivia {game_date} must contain exactly ten questions."
            )
        for index, question in enumerate(questions, 1):
            options = question.get("options") or []
            try:
                answer = int(question.get("answer"))
            except (TypeError, ValueError):
                answer = -1
            if not str(question.get("prompt") or "").strip():
                raise click.ClickException(
                    f"Trivia {game_date} question {index} has no prompt."
                )
            if len(options) != 4 or any(not str(option).strip() for option in options):
                raise click.ClickException(
                    f"Trivia {game_date} question {index} needs four answer choices."
                )
            if answer not in range(4):
                raise click.ClickException(
                    f"Trivia {game_date} question {index} has an invalid answer index."
                )

    return game_key, game_date, theme_label, content


def init_app(app):
    @app.cli.command("import-question-bank")
    @click.option(
        "--only",
        "only_game",
        type=click.Choice(["all", "mystery", "trivia"], case_sensitive=False),
        default="all",
        show_default=True,
        help="Import both games or only one question bank.",
    )
    @click.option(
        "--status",
        type=click.Choice(["draft", "published"], case_sensitive=False),
        default="published",
        show_default=True,
        help="Status to assign to imported scheduled content.",
    )
    @click.option(
        "--replace",
        is_flag=True,
        help="Replace existing future content only when no player has started that game date.",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        help="Validate and report changes without writing to the database.",
    )
    def import_question_bank_command(only_game, status, replace, dry_run):
        """Load the curated Mystery Monday and Trivia Tuesday banks into game_content."""
        payload = _load_bank()
        entries = []
        for game_key in ("mystery", "trivia"):
            if only_game != "all" and only_game != game_key:
                continue
            raw_entries = payload.get(game_key) or []
            if not isinstance(raw_entries, list):
                raise click.ClickException(f"{game_key} question bank is invalid.")
            entries.extend(raw_entries)

        created = 0
        replaced = 0
        skipped_existing = 0
        skipped_locked = 0

        for raw_entry in entries:
            game_key, game_date, theme_label, content = _validate_entry(raw_entry)
            existing = get_game_content(game_key, game_date)

            if existing:
                if not replace:
                    skipped_existing += 1
                    continue
                if count_game_attempts(game_key, game_date) > 0:
                    skipped_locked += 1
                    continue
                replaced += 1
            else:
                created += 1

            if not dry_run:
                save_game_content(
                    game_key,
                    game_date,
                    theme_label,
                    content,
                    status=status,
                )

        prefix = "DRY RUN — " if dry_run else ""
        click.echo(
            f"{prefix}Question bank import: "
            f"{created} created, {replaced} replaced, "
            f"{skipped_existing} skipped existing, {skipped_locked} skipped locked."
        )

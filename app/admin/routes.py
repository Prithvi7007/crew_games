import hmac
import re
from datetime import date, timedelta
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.db import (
    count_game_attempts,
    get_game_content,
    save_game_content,
    set_game_content_status,
)
from app.mystery.game import get_puzzle
from app.schedule import crew_today, GAME_DEFINITIONS, get_game_definition, get_week_start
from app.tick_tock.game import get_target
from app.trivia.game import get_quiz
from app.word.game import get_daily_solution


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("crew_admin"):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _parse_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _week_from_query():
    requested = _parse_day(request.args.get("week"))
    return get_week_start(requested or crew_today())


def _validate_slot(game_key, game_day):
    try:
        definition = get_game_definition(game_key)
    except StopIteration:
        return None
    if game_day.weekday() != definition["weekday"]:
        return None
    return definition


def _fallback_content(game_key, game_day):
    if game_key == "mystery":
        puzzle = get_puzzle(game_day)
        return {
            "theme_label": puzzle.get("theme", ""),
            "content": {
                "answer": puzzle["answer"],
                "accepted": sorted(puzzle["accepted"]),
                "clues": list(puzzle["clues"]),
            },
        }
    if game_key == "trivia":
        quiz = get_quiz(game_day)
        return {
            "theme_label": quiz.get("theme", ""),
            "content": {
                "questions": [
                    {
                        "prompt": question["prompt"],
                        "options": list(question["options"]),
                        "answer": int(question["answer"]),
                    }
                    for question in quiz["questions"]
                ]
            },
        }
    if game_key == "word":
        return {
            "theme_label": "",
            "content": {"solution": get_daily_solution(game_day)},
        }
    if game_key == "tick_tock":
        return {
            "theme_label": "",
            "content": {"target_seconds": float(get_target(game_day))},
        }
    raise ValueError("Unknown game key")


def _editor_payload(game_key, game_day):
    row = get_game_content(game_key, game_day.isoformat())
    if row:
        return {
            "theme_label": row["theme_label"],
            "content": row["content"],
            "status": row["status"],
            "updated_at": row["updated_at"],
            "published_at": row["published_at"],
            "source": "scheduled",
        }
    fallback = _fallback_content(game_key, game_day)
    return {
        **fallback,
        "status": "fallback",
        "updated_at": None,
        "published_at": None,
        "source": "fallback",
    }


def _split_accepted(raw):
    parts = re.split(r"[,\n]", raw or "")
    return [part.strip() for part in parts if part.strip()]


def _parse_content_form(game_key):
    theme_label = request.form.get("theme_label", "").strip()[:80]

    if game_key == "mystery":
        answer = request.form.get("answer", "").strip()
        accepted = _split_accepted(request.form.get("accepted", ""))
        clues = [request.form.get(f"clue_{i}", "").strip() for i in range(1, 6)]
        if not answer or len(answer) > 80:
            return None, None, "Enter a mystery answer of 80 characters or fewer."
        if any(not clue for clue in clues):
            return None, None, "Mystery Monday needs all five clues."
        if not accepted:
            accepted = [answer]
        if answer.casefold() not in {item.casefold() for item in accepted}:
            accepted.insert(0, answer)
        return theme_label, {"answer": answer, "accepted": accepted, "clues": clues}, None

    if game_key == "trivia":
        questions = []
        for i in range(1, 11):
            prompt = request.form.get(f"q{i}_prompt", "").strip()
            options = [request.form.get(f"q{i}_{letter}", "").strip() for letter in "abcd"]
            answer_raw = request.form.get(f"q{i}_answer", "")
            try:
                answer = int(answer_raw)
            except ValueError:
                answer = -1
            if not prompt or any(not option for option in options):
                return None, None, f"Question {i} needs a prompt and four answer choices."
            if answer not in range(4):
                return None, None, f"Choose the correct answer for question {i}."
            questions.append({"prompt": prompt, "options": options, "answer": answer})
        return theme_label, {"questions": questions}, None

    if game_key == "word":
        solution = request.form.get("solution", "").strip().upper()
        if len(solution) != 5 or not solution.isalpha():
            return None, None, "Wordle Wednesday needs a five-letter alphabetic answer."
        return theme_label, {"solution": solution}, None

    if game_key == "tick_tock":
        try:
            target = float(request.form.get("target_seconds", ""))
        except ValueError:
            return None, None, "Enter a valid timer target."
        if not 2.0 <= target <= 30.0:
            return None, None, "Use a Tick-Tock target between 2 and 30 seconds."
        return theme_label, {"target_seconds": round(target, 2)}, None

    return None, None, "Unknown game type."


def _content_summary(game_key, payload):
    content = payload["content"]
    if game_key == "mystery":
        return f"Answer: {content.get('answer', '—')} · {len(content.get('clues', []))} clues"
    if game_key == "trivia":
        return f"{len(content.get('questions', []))} questions"
    if game_key == "word":
        return f"Answer: {content.get('solution', '—')}"
    if game_key == "tick_tock":
        target = content.get("target_seconds")
        return f"Target: {target:.2f} sec" if isinstance(target, (int, float)) else "Timer target"
    return ""


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if hmac.compare_digest(password, current_app.config["CREW_ADMIN_PASSWORD"]):
            session.permanent = True
            session["crew_admin"] = True
            return redirect(url_for("admin.dashboard"))
        flash("That admin passphrase isn't valid.", "error")
    return render_template("admin/login.html")


@admin_bp.post("/logout")
@admin_required
def logout():
    session.pop("crew_admin", None)
    return redirect(url_for("admin.login"))


@admin_bp.get("")
@admin_required
def dashboard():
    week_start = _week_from_query()
    items = []
    for definition in GAME_DEFINITIONS:
        game_day = week_start + timedelta(days=definition["weekday"])
        payload = _editor_payload(definition["key"], game_day)
        attempts = count_game_attempts(definition["key"], game_day.isoformat())
        items.append({
            **definition,
            "date": game_day,
            "status": payload["status"],
            "theme_label": payload["theme_label"],
            "summary": _content_summary(definition["key"], payload),
            "attempts": attempts,
            "locked": attempts > 0,
            "edit_url": url_for("admin.edit_game", game_key=definition["key"], game_date=game_day.isoformat()),
            "preview_url": url_for("admin.preview_game", game_key=definition["key"], game_date=game_day.isoformat()),
        })

    return render_template(
        "admin/dashboard.html",
        week_start=week_start,
        week_end=week_start + timedelta(days=3),
        previous_week=week_start - timedelta(days=7),
        next_week=week_start + timedelta(days=7),
        items=items,
    )


@admin_bp.route("/game/<game_key>/<game_date>", methods=["GET", "POST"])
@admin_required
def edit_game(game_key, game_date):
    game_day = _parse_day(game_date)
    definition = _validate_slot(game_key, game_day) if game_day else None
    if not definition:
        flash("That CREW game slot isn't valid.", "error")
        return redirect(url_for("admin.dashboard"))

    attempts = count_game_attempts(game_key, game_date)
    locked = attempts > 0

    if request.method == "POST":
        if locked:
            flash("This game is locked because at least one player has started it.", "error")
        else:
            action = request.form.get("action", "draft")
            if action == "unpublish":
                if set_game_content_status(game_key, game_date, "draft"):
                    flash("Game returned to draft. Players will use the fallback until you publish again.", "success")
                else:
                    flash("There isn't scheduled content to unpublish yet.", "error")
                return redirect(url_for("admin.edit_game", game_key=game_key, game_date=game_date))

            theme_label, content, error = _parse_content_form(game_key)
            if error:
                flash(error, "error")
            else:
                status = "published" if action == "publish" else "draft"
                save_game_content(game_key, game_date, theme_label, content, status=status)
                if status == "published":
                    flash("Published. This content is now live for that CREW game date.", "success")
                else:
                    flash("Draft saved. Preview it before publishing when you're ready.", "success")
                return redirect(url_for("admin.edit_game", game_key=game_key, game_date=game_date))

    payload = _editor_payload(game_key, game_day)
    return render_template(
        "admin/editor.html",
        definition=definition,
        game_day=game_day,
        payload=payload,
        locked=locked,
        attempts=attempts,
        preview_url=url_for("admin.preview_game", game_key=game_key, game_date=game_date),
        dashboard_url=url_for("admin.dashboard", week=get_week_start(game_day).isoformat()),
    )


@admin_bp.get("/preview/<game_key>/<game_date>")
@admin_required
def preview_game(game_key, game_date):
    game_day = _parse_day(game_date)
    definition = _validate_slot(game_key, game_day) if game_day else None
    if not definition:
        flash("That CREW game slot isn't valid.", "error")
        return redirect(url_for("admin.dashboard"))
    payload = _editor_payload(game_key, game_day)
    return render_template(
        "admin/preview.html",
        definition=definition,
        game_day=game_day,
        payload=payload,
        edit_url=url_for("admin.edit_game", game_key=game_key, game_date=game_date),
    )

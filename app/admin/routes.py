import hmac
import re
import secrets
import time
from datetime import date, timedelta
from functools import wraps

from werkzeug.security import generate_password_hash

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
    get_db,
    get_game_content,
    get_profile_by_id,
    save_game_content,
    set_game_content_status,
    update_profile_password,
    update_profile_recovery_code,
)
from app.mystery.game import get_puzzle
from app.schedule import crew_today, GAME_DEFINITIONS, get_game_definition, get_week_start
from app.tick_tock.game import get_target
from app.trivia.game import get_quiz
from app.word.game import get_daily_solution
from app.security import (
    admin_session_fingerprint,
    audit_security_event,
    clear_rate_limits,
    enforce_rate_limits,
    limit_policy,
    record_rate_limit_failures,
    verify_totp,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        fingerprint = session.get("crew_admin")
        authenticated_at = float(session.get("crew_admin_at", 0) or 0)
        max_age = current_app.config["ADMIN_SESSION_HOURS"] * 3600
        valid = (
            fingerprint
            and hmac.compare_digest(str(fingerprint), admin_session_fingerprint())
            and authenticated_at > 0
            and time.time() - authenticated_at <= max_age
        )
        if not valid:
            session.pop("crew_admin", None)
            session.pop("crew_admin_at", None)
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


def _plain_text(value, max_length):
    value = str(value or "").replace("\x00", "").strip()
    value = " ".join(value.split())
    return value[:max_length]


def _split_accepted(raw):
    parts = re.split(r"[,\n]", raw or "")
    return [_plain_text(part, 80) for part in parts if part.strip()][:20]


def _parse_content_form(game_key):
    theme_label = _plain_text(request.form.get("theme_label", ""), 80)

    if game_key == "mystery":
        answer = _plain_text(request.form.get("answer", ""), 80)
        accepted = _split_accepted(request.form.get("accepted", ""))
        clues = [_plain_text(request.form.get(f"clue_{i}", ""), 280) for i in range(1, 5)]
        if not answer or len(answer) > 80:
            return None, None, "Enter a mystery answer of 80 characters or fewer."
        if any(not clue for clue in clues):
            return None, None, "Mystery Monday needs all four clues."
        if not accepted:
            accepted = [answer]
        if answer.casefold() not in {item.casefold() for item in accepted}:
            accepted.insert(0, answer)
        return theme_label, {"answer": answer, "accepted": accepted, "clues": clues}, None

    if game_key == "trivia":
        questions = []
        for i in range(1, 11):
            prompt = _plain_text(request.form.get(f"q{i}_prompt", ""), 500)
            options = [_plain_text(request.form.get(f"q{i}_{letter}", ""), 240) for letter in "abcd"]
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
    policy = limit_policy(
        "admin-login",
        "content-studio",
        current_app.config["ADMIN_RATE_LIMIT_ATTEMPTS"],
        current_app.config["ADMIN_RATE_LIMIT_WINDOW"],
    )
    totp_enabled = bool(current_app.config.get("CREW_ADMIN_TOTP_SECRET"))
    if request.method == "POST":
        if blocked := enforce_rate_limits(policy):
            return blocked
        password = request.form.get("password", "")
        otp = request.form.get("otp", "")
        password_ok = hmac.compare_digest(password, current_app.config["CREW_ADMIN_PASSWORD"])
        totp_ok = (not totp_enabled) or verify_totp(current_app.config["CREW_ADMIN_TOTP_SECRET"], otp)
        if password_ok and totp_ok:
            clear_rate_limits(policy)
            session.permanent = True
            session["crew_admin"] = admin_session_fingerprint()
            session["crew_admin_at"] = time.time()
            audit_security_event("admin_login_success", "content-studio", {"totp": totp_enabled})
            return redirect(url_for("admin.dashboard"))
        record_rate_limit_failures(policy)
        audit_security_event("admin_login_failure", "content-studio", {"totp": totp_enabled})
        flash("That admin sign-in isn't valid.", "error")
    return render_template("admin/login.html", totp_enabled=totp_enabled)


@admin_bp.post("/logout")
@admin_required
def logout():
    audit_security_event("admin_logout", "content-studio")
    session.pop("crew_admin", None)
    session.pop("crew_admin_at", None)
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
                    audit_security_event("admin_content_unpublished", f"{game_key}:{game_date}")
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
                audit_security_event(f"admin_content_{status}", f"{game_key}:{game_date}")
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


PLAYER_GAME_LABELS = {
    "mystery": "Mystery Monday",
    "trivia": "Trivia Tuesday",
    "word": "Wordle Wednesday",
    "tick_tock": "Tick-Tock Thursday",
}


def _player_admin_rows(search=""):
    search = _plain_text(search, 40)
    where = ""
    params = []
    if search:
        where = "WHERE LOWER(p.username) LIKE ?"
        params.append(f"%{search.casefold()}%")

    rows = get_db().execute(
        f"""
        SELECT
            p.id, p.username, p.avatar, p.created_at, p.last_login_at, p.session_version,
            COALESCE(us.current_streak, 0) AS current_streak,
            COALESCE(us.longest_streak, 0) AS longest_streak,
            COALESCE(us.total_points, 0) AS total_points,
            COALESCE(us.games_completed, 0) AS games_completed,
            (
                SELECT MAX(gc.completed_at)
                FROM game_completions gc
                WHERE gc.profile_id = p.id AND gc.competitive = 1
            ) AS last_played_at
        FROM profiles p
        LEFT JOIN user_stats us ON us.profile_id = p.id
        {where}
        ORDER BY LOWER(p.username) ASC
        """,
        params,
    ).fetchall()

    players = []
    for row in rows:
        item = dict(row)
        activity = [value for value in (item.get("last_login_at"), item.get("last_played_at")) if value]
        item["last_activity"] = max(activity) if activity else None
        players.append(item)
    return players


def _player_admin_record(profile_id):
    profile = get_profile_by_id(profile_id)
    if not profile:
        return None
    stats = get_db().execute(
        """
        SELECT current_streak, longest_streak, total_points, games_completed, last_completed_date
        FROM user_stats
        WHERE profile_id = ?
        """,
        (profile_id,),
    ).fetchone()
    result = dict(profile)
    result.update({
        "current_streak": int(stats["current_streak"]) if stats else 0,
        "longest_streak": int(stats["longest_streak"]) if stats else 0,
        "total_points": int(stats["total_points"]) if stats else 0,
        "games_completed": int(stats["games_completed"]) if stats else 0,
        "last_completed_date": stats["last_completed_date"] if stats else None,
    })
    return result


def _player_recent_games(profile_id, limit=20):
    rows = get_db().execute(
        """
        SELECT game_key, game_date, score, won, completed_at, competitive
        FROM game_completions
        WHERE profile_id = ?
        ORDER BY game_date DESC, completed_at DESC
        LIMIT ?
        """,
        (profile_id, limit),
    ).fetchall()
    games = []
    for row in rows:
        item = dict(row)
        item["title"] = PLAYER_GAME_LABELS.get(item["game_key"], item["game_key"].replace("_", " ").title())
        games.append(item)
    return games


def _render_player_detail(profile_id, credential_result=None):
    player = _player_admin_record(profile_id)
    if not player:
        flash("That player account no longer exists.", "error")
        return redirect(url_for("admin.players"))
    return render_template(
        "admin/player_detail.html",
        player=player,
        recent_games=_player_recent_games(profile_id),
        credential_result=credential_result,
    )


def _invalidate_player_sessions(profile_id):
    db = get_db()
    result = db.execute(
        "UPDATE profiles SET session_version = session_version + 1 WHERE id = ?",
        (profile_id,),
    )
    db.commit()
    return result.rowcount > 0


@admin_bp.get("/players")
@admin_required
def players():
    search = _plain_text(request.args.get("q", ""), 40)
    players = _player_admin_rows(search)
    all_players = players if not search else _player_admin_rows()
    active_cutoff = (crew_today() - timedelta(days=6)).isoformat()
    metrics = {
        "players": len(all_players),
        "active": sum(
            1 for player in all_players
            if player.get("last_activity") and str(player["last_activity"])[:10] >= active_cutoff
        ),
        "games": sum(int(player.get("games_completed") or 0) for player in all_players),
    }
    return render_template(
        "admin/players.html",
        players=players,
        search=search,
        metrics=metrics,
    )


@admin_bp.get("/players/<int:profile_id>")
@admin_required
def player_detail(profile_id):
    return _render_player_detail(profile_id)


@admin_bp.post("/players/<int:profile_id>/force-sign-out")
@admin_required
def player_force_sign_out(profile_id):
    player = get_profile_by_id(profile_id)
    if not player:
        flash("That player account no longer exists.", "error")
        return redirect(url_for("admin.players"))
    _invalidate_player_sessions(profile_id)
    audit_security_event("admin_player_force_sign_out", player["username"], {"profile_id": profile_id})
    flash(f"{player['username']} will be signed out on their next authenticated request.", "success")
    return redirect(url_for("admin.player_detail", profile_id=profile_id))


@admin_bp.post("/players/<int:profile_id>/reset-password")
@admin_required
def player_reset_password(profile_id):
    player = get_profile_by_id(profile_id)
    if not player:
        flash("That player account no longer exists.", "error")
        return redirect(url_for("admin.players"))
    temporary_password = secrets.token_urlsafe(14)
    update_profile_password(profile_id, generate_password_hash(temporary_password))
    audit_security_event("admin_player_password_reset", player["username"], {"profile_id": profile_id})
    return _render_player_detail(profile_id, {
        "kind": "password",
        "title": "Temporary password",
        "value": temporary_password,
        "message": "Give this to the player securely. Their previous sessions are now invalid.",
    })


@admin_bp.post("/players/<int:profile_id>/reset-recovery")
@admin_required
def player_reset_recovery(profile_id):
    player = get_profile_by_id(profile_id)
    if not player:
        flash("That player account no longer exists.", "error")
        return redirect(url_for("admin.players"))
    recovery_code = "CREW-" + "-".join(secrets.token_hex(3).upper() for _ in range(3))
    update_profile_recovery_code(profile_id, generate_password_hash(recovery_code))
    audit_security_event("admin_player_recovery_reset", player["username"], {"profile_id": profile_id})
    return _render_player_detail(profile_id, {
        "kind": "recovery",
        "title": "New recovery code",
        "value": recovery_code,
        "message": "This replaces the player's previous recovery code. Show it once and store it securely.",
    })

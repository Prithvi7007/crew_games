import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from functools import wraps

from cryptography.fernet import Fernet, InvalidToken
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import (
    create_profile,
    ensure_user_stats,
    get_profile_by_id,
    get_profile_by_username,
    get_profile_history_summary,
    profile_user_key,
    touch_profile_login,
    update_profile_avatar,
    update_profile_credentials,
    update_profile_password,
    update_profile_recovery_code,
)
from app.security import (
    audit_security_event,
    clear_rate_limits,
    enforce_rate_limits,
    limit_policy,
    record_rate_limit_failures,
)


auth_bp = Blueprint("auth", __name__)

AVATARS = [
    {"value": "🎢", "label": "Coaster"},
    {"value": "🦖", "label": "Dinosaur"},
    {"value": "🤖", "label": "Robot"},
    {"value": "🍌", "label": "Banana"},
    {"value": "🎬", "label": "Movies"},
    {"value": "⭐", "label": "Star"},
    {"value": "🚀", "label": "Rocket"},
    {"value": "🧩", "label": "Puzzle"},
    {"value": "🏆", "label": "Trophy"},
    {"value": "🌎", "label": "World"},
    {"value": "🦈", "label": "Shark"},
    {"value": "✨", "label": "Spark"},
]
AVATAR_VALUES = {item["value"] for item in AVATARS}
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,24}$")
RESERVED_USERNAMES = {"admin", "administrator", "crew", "universal", "support", "moderator"}
RECOVERY_WORDS = (
    "ORBIT", "NOVA", "COMET", "RIVER", "MANGO", "PIXEL", "ROCKET", "TIDAL",
    "QUEST", "CLOUD", "SPARK", "GALAXY", "CORAL", "JUNGLE", "STUDIO", "COSMIC",
    "MAPLE", "SUNSET", "PORTAL", "WONDER", "CANYON", "NEON", "LAGOON", "SUMMIT",
    "SAFARI", "AURORA", "VOYAGE", "RAPTOR", "CINEMA", "PLANET", "HARBOR", "TEMPO",
)
COMMON_PASSWORDS = {
    "password1234", "password123!", "123456789012", "qwerty123456", "letmein123456",
    "crewcrewcrew", "universal123", "welcome12345", "adminadmin123", "iloveyou1234",
}
_RECOVERY_DISPLAY_TTL_SECONDS = 300
_DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32))
_DUMMY_RECOVERY_HASH = generate_password_hash(secrets.token_urlsafe(32))


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = session.get("user")
        if not user or not user.get("user_key") or not user.get("profile_id"):
            session.clear()
            return redirect(url_for("auth.login", next=request.path))
        profile = get_profile_by_id(user["profile_id"])
        if not profile or int(profile["session_version"] or 1) != int(user.get("session_version", 0)):
            session.clear()
            flash("Your session has expired. Sign in again.", "error")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def current_user_key():
    return session["user"]["user_key"]


def _safe_next(default_endpoint="main.home"):
    target = request.args.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return target
    return url_for(default_endpoint)


def _profile_session(profile):
    return {
        "profile_id": int(profile["id"]),
        "username": profile["username"],
        "avatar": profile["avatar"],
        "user_key": profile_user_key(profile["id"]),
        "session_version": int(profile["session_version"] or 1),
    }


def _sign_in(profile):
    session.clear()
    session.permanent = True
    session["user"] = _profile_session(profile)
    touch_profile_login(profile["id"])
    ensure_user_stats(profile_user_key(profile["id"]))


def _generate_recovery_code():
    words = [secrets.choice(RECOVERY_WORDS) for _ in range(4)]
    suffix = secrets.token_hex(2).upper()
    return "-".join([*words, suffix])


def _recovery_cipher():
    digest = hashlib.sha256(current_app.config["SECRET_KEY"].encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _stash_recovery_display(code, context, profile_id):
    payload = json.dumps({
        "code": code,
        "context": context,
        "profile_id": int(profile_id),
        "expires_at": time.time() + _RECOVERY_DISPLAY_TTL_SECONDS,
    }).encode("utf-8")
    session["recovery_display"] = _recovery_cipher().encrypt(payload).decode("ascii")


def _validate_password(password, confirmation, username=""):
    minimum = int(current_app.config["PASSWORD_MIN_LENGTH"])
    maximum = int(current_app.config["PASSWORD_MAX_LENGTH"])
    if len(password) < minimum:
        return f"Use at least {minimum} characters for your password."
    if len(password) > maximum:
        return f"Use no more than {maximum} characters for your password."
    if password.casefold() in COMMON_PASSWORDS:
        return "Choose a less common password or passphrase."
    if username and len(username) >= 4 and username.casefold() in password.casefold():
        return "Your password should not contain your CREW name."
    if password != confirmation:
        return "Those passwords don't match."
    return None


def _login_policies(username):
    return (
        limit_policy(
            "player-login-account",
            username,
            current_app.config["LOGIN_RATE_LIMIT_ATTEMPTS"],
            current_app.config["LOGIN_RATE_LIMIT_WINDOW"],
        ),
        limit_policy(
            "player-login-ip",
            "",
            current_app.config["AUTH_IP_RATE_LIMIT_ATTEMPTS"],
            current_app.config["AUTH_IP_RATE_LIMIT_WINDOW"],
        ),
    )


def _recovery_policies(username):
    return (
        limit_policy(
            "player-recovery-account",
            username,
            current_app.config["RECOVERY_RATE_LIMIT_ATTEMPTS"],
            current_app.config["RECOVERY_RATE_LIMIT_WINDOW"],
        ),
        limit_policy(
            "player-recovery-ip",
            "",
            current_app.config["AUTH_IP_RATE_LIMIT_ATTEMPTS"],
            current_app.config["AUTH_IP_RATE_LIMIT_WINDOW"],
        ),
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        policies = _login_policies(username)
        if blocked := enforce_rate_limits(*policies):
            return blocked

        profile = get_profile_by_username(username) if username else None
        password_hash = profile["password_hash"] if profile else _DUMMY_PASSWORD_HASH
        password_ok = check_password_hash(password_hash, password)

        if profile and password_ok:
            clear_rate_limits(*policies)
            audit_security_event("player_login_success", username)
            _sign_in(profile)
            return redirect(_safe_next())

        record_rate_limit_failures(*policies)
        audit_security_event("player_login_failure", username)
        flash("We couldn't sign you in with that CREW name and password.", "error")

    return render_template("login.html")


@auth_bp.route("/create-profile", methods=["GET", "POST"])
def create_profile_view():
    selected_avatar = request.form.get("avatar", AVATARS[0]["value"])
    entered_username = request.form.get("username", "").strip()

    if request.method == "POST":
        policy = limit_policy(
            "profile-create-ip",
            "",
            current_app.config["PROFILE_CREATE_RATE_LIMIT_ATTEMPTS"],
            current_app.config["PROFILE_CREATE_RATE_LIMIT_WINDOW"],
        )
        if blocked := enforce_rate_limits(policy):
            return blocked

        invite_code = request.form.get("invite_code", "").strip()
        password = request.form.get("password", "")
        confirmation = request.form.get("password_confirm", "")
        error = None

        if not hmac.compare_digest(invite_code, current_app.config["CREW_INVITE_CODE"]):
            error = "That CREW invitation code isn't valid."
        elif not USERNAME_RE.fullmatch(entered_username):
            error = "CREW names must be 3–24 characters using letters, numbers, _ or -."
        elif entered_username.lower() in RESERVED_USERNAMES:
            error = "That CREW name is reserved. Pick another one."
        elif selected_avatar not in AVATAR_VALUES:
            error = "Choose one of the CREW avatars."
        elif get_profile_by_username(entered_username):
            error = "That CREW name is already taken."
        elif password_error := _validate_password(password, confirmation, entered_username):
            error = password_error

        if error:
            record_rate_limit_failures(policy)
            audit_security_event("profile_create_failure", entered_username)
            flash(error, "error")
        else:
            recovery_code = _generate_recovery_code()
            try:
                profile = create_profile(
                    entered_username,
                    generate_password_hash(password),
                    selected_avatar,
                    generate_password_hash(recovery_code),
                )
            except IntegrityError:
                record_rate_limit_failures(policy)
                audit_security_event("profile_create_race", entered_username)
                flash("That CREW name was just claimed. Pick another one.", "error")
            else:
                clear_rate_limits(policy)
                audit_security_event("profile_create_success", entered_username)
                _sign_in(profile)
                _stash_recovery_display(recovery_code, "created", profile["id"])
                return redirect(url_for("auth.recovery_code"))

    return render_template(
        "create_profile.html",
        avatars=AVATARS,
        selected_avatar=selected_avatar,
        entered_username=entered_username,
        password_min_length=current_app.config["PASSWORD_MIN_LENGTH"],
    )


@auth_bp.route("/recover", methods=["GET", "POST"])
def recover():
    entered_username = request.form.get("username", "").strip()

    if request.method == "POST":
        policies = _recovery_policies(entered_username)
        if blocked := enforce_rate_limits(*policies):
            return blocked

        recovery_code = request.form.get("recovery_code", "").strip().upper()
        password = request.form.get("password", "")
        confirmation = request.form.get("password_confirm", "")
        profile = get_profile_by_username(entered_username) if entered_username else None
        recovery_hash = profile["recovery_code_hash"] if profile else _DUMMY_RECOVERY_HASH
        recovery_ok = check_password_hash(recovery_hash, recovery_code)
        password_error = _validate_password(password, confirmation, entered_username)

        if not profile or not recovery_ok:
            record_rate_limit_failures(*policies)
            audit_security_event("player_recovery_failure", entered_username)
            flash("That CREW name and recovery code combination isn't valid.", "error")
        elif password_error:
            record_rate_limit_failures(*policies)
            flash(password_error, "error")
        else:
            new_recovery_code = _generate_recovery_code()
            profile = update_profile_credentials(
                profile["id"],
                generate_password_hash(password),
                generate_password_hash(new_recovery_code),
            )
            clear_rate_limits(*policies)
            audit_security_event("player_recovery_success", entered_username)
            _sign_in(profile)
            _stash_recovery_display(new_recovery_code, "reset", profile["id"])
            return redirect(url_for("auth.recovery_code"))

    return render_template(
        "recover.html",
        entered_username=entered_username,
        password_min_length=current_app.config["PASSWORD_MIN_LENGTH"],
    )


@auth_bp.get("/recovery-code")
@login_required
def recovery_code():
    token = session.pop("recovery_display", None)
    item = None
    if token:
        try:
            payload = _recovery_cipher().decrypt(token.encode("ascii"), ttl=_RECOVERY_DISPLAY_TTL_SECONDS + 30)
            item = json.loads(payload.decode("utf-8"))
        except (InvalidToken, ValueError, TypeError, json.JSONDecodeError):
            item = None
    if (
        not item
        or item.get("expires_at", 0) <= time.time()
        or item.get("profile_id") != session["user"]["profile_id"]
    ):
        flash("That recovery code display has expired or was already shown.", "error")
        return redirect(url_for("main.home"))

    return render_template(
        "recovery_code.html",
        recovery_code=item["code"],
        recovery_context=item["context"],
        user=session["user"],
    )


@auth_bp.post("/recovery-code/continue")
@login_required
def recovery_code_continue():
    target = request.form.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return redirect(target)
    return redirect(url_for("main.home"))


@auth_bp.post("/logout")
def logout():
    if session.get("user"):
        audit_security_event("player_logout", session["user"].get("username", ""))
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.get("/profile")
@login_required
def profile():
    profile_row = get_profile_by_id(session["user"]["profile_id"])
    stats = ensure_user_stats(current_user_key())
    history = get_profile_history_summary(current_user_key())
    return render_template(
        "profile.html",
        user=session["user"],
        profile=profile_row,
        avatars=AVATARS,
        stats=stats,
        history=history,
        password_min_length=current_app.config["PASSWORD_MIN_LENGTH"],
    )


@auth_bp.post("/profile/avatar")
@login_required
def profile_avatar():
    avatar = request.form.get("avatar", "")
    if avatar not in AVATAR_VALUES:
        flash("Choose one of the CREW avatars.", "error")
    else:
        profile_row = update_profile_avatar(session["user"]["profile_id"], avatar)
        session["user"]["avatar"] = profile_row["avatar"]
        session.modified = True
        flash("Avatar updated.", "success")
    return redirect(url_for("auth.profile"))


@auth_bp.post("/profile/password")
@login_required
def profile_password():
    username = session["user"]["username"]
    policy = limit_policy(
        "profile-password",
        username,
        current_app.config["RECOVERY_RATE_LIMIT_ATTEMPTS"],
        current_app.config["RECOVERY_RATE_LIMIT_WINDOW"],
    )
    if blocked := enforce_rate_limits(policy):
        return blocked

    profile_row = get_profile_by_id(session["user"]["profile_id"])
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirmation = request.form.get("new_password_confirm", "")
    if not check_password_hash(profile_row["password_hash"], current_password):
        record_rate_limit_failures(policy)
        audit_security_event("profile_password_failure", username)
        flash("Your current password is not correct.", "error")
    elif password_error := _validate_password(new_password, confirmation, username):
        record_rate_limit_failures(policy)
        flash(password_error, "error")
    elif check_password_hash(profile_row["password_hash"], new_password):
        record_rate_limit_failures(policy)
        flash("Choose a password different from your current one.", "error")
    else:
        profile_row = update_profile_password(profile_row["id"], generate_password_hash(new_password))
        clear_rate_limits(policy)
        _sign_in(profile_row)  # New session version revokes every other browser session.
        audit_security_event("profile_password_changed", username)
        flash("Password changed. Other signed-in sessions were revoked.", "success")
    return redirect(url_for("auth.profile"))


@auth_bp.post("/profile/recovery")
@login_required
def profile_recovery():
    username = session["user"]["username"]
    policy = limit_policy(
        "profile-recovery-code",
        username,
        current_app.config["RECOVERY_RATE_LIMIT_ATTEMPTS"],
        current_app.config["RECOVERY_RATE_LIMIT_WINDOW"],
    )
    if blocked := enforce_rate_limits(policy):
        return blocked

    profile_row = get_profile_by_id(session["user"]["profile_id"])
    current_password = request.form.get("current_password", "")
    if not check_password_hash(profile_row["password_hash"], current_password):
        record_rate_limit_failures(policy)
        audit_security_event("profile_recovery_rotate_failure", username)
        flash("Enter your current password to generate a new recovery code.", "error")
        return redirect(url_for("auth.profile"))
    new_code = _generate_recovery_code()
    update_profile_recovery_code(profile_row["id"], generate_password_hash(new_code))
    clear_rate_limits(policy)
    audit_security_event("profile_recovery_rotated", username)
    _stash_recovery_display(new_code, "regenerated", profile_row["id"])
    return redirect(url_for("auth.recovery_code"))

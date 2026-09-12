import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.exc import IntegrityError

from app.db import (
    create_profile,
    ensure_user_stats,
    get_profile_by_username,
    profile_user_key,
    touch_profile_login,
    update_profile_credentials,
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

_RECOVERY_DISPLAY_TTL_SECONDS = 300


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = session.get("user")
        if not user or not user.get("user_key"):
            session.clear()
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
    # Encrypt the one-time recovery display before it is placed in Flask's
    # client-side session cookie. This keeps the readable recovery code out of
    # the database and makes the flow safe across multiple Gunicorn workers.
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


def _validate_password(password, confirmation):
    if len(password) < 8:
        return "Use at least 8 characters for your password."
    if password != confirmation:
        return "Those passwords don't match."
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        profile = get_profile_by_username(username) if username else None

        if profile and check_password_hash(profile["password_hash"], password):
            _sign_in(profile)
            return redirect(_safe_next())

        flash("We couldn't sign you in with that CREW name and password.", "error")

    return render_template("login.html")


@auth_bp.route("/create-profile", methods=["GET", "POST"])
def create_profile_view():
    selected_avatar = request.form.get("avatar", AVATARS[0]["value"])
    entered_username = request.form.get("username", "").strip()

    if request.method == "POST":
        invite_code = request.form.get("invite_code", "").strip()
        password = request.form.get("password", "")
        confirmation = request.form.get("password_confirm", "")

        if not hmac.compare_digest(invite_code, current_app.config["CREW_INVITE_CODE"]):
            flash("That CREW invitation code isn't valid.", "error")
        elif not USERNAME_RE.fullmatch(entered_username):
            flash("CREW names must be 3–24 characters using letters, numbers, _ or -.", "error")
        elif entered_username.lower() in RESERVED_USERNAMES:
            flash("That CREW name is reserved. Pick another one.", "error")
        elif selected_avatar not in AVATAR_VALUES:
            flash("Choose one of the CREW avatars.", "error")
        elif get_profile_by_username(entered_username):
            flash("That CREW name is already taken.", "error")
        elif (password_error := _validate_password(password, confirmation)):
            flash(password_error, "error")
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
                flash("That CREW name was just claimed. Pick another one.", "error")
            else:
                _sign_in(profile)
                _stash_recovery_display(recovery_code, "created", profile["id"])
                return redirect(url_for("auth.recovery_code"))

    return render_template(
        "create_profile.html",
        avatars=AVATARS,
        selected_avatar=selected_avatar,
        entered_username=entered_username,
    )


@auth_bp.route("/recover", methods=["GET", "POST"])
def recover():
    entered_username = request.form.get("username", "").strip()

    if request.method == "POST":
        recovery_code = request.form.get("recovery_code", "").strip().upper()
        password = request.form.get("password", "")
        confirmation = request.form.get("password_confirm", "")
        profile = get_profile_by_username(entered_username) if entered_username else None
        password_error = _validate_password(password, confirmation)

        if not profile or not check_password_hash(profile["recovery_code_hash"], recovery_code):
            flash("That CREW name and recovery code combination isn't valid.", "error")
        elif password_error:
            flash(password_error, "error")
        else:
            new_recovery_code = _generate_recovery_code()
            update_profile_credentials(
                profile["id"],
                generate_password_hash(password),
                generate_password_hash(new_recovery_code),
            )
            _sign_in(profile)
            _stash_recovery_display(new_recovery_code, "reset", profile["id"])
            return redirect(url_for("auth.recovery_code"))

    return render_template("recover.html", entered_username=entered_username)


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
    return redirect(url_for("main.home"))


@auth_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

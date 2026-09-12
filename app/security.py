import hmac
import secrets

from flask import abort, jsonify, request, session


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _csrf_failure():
    accepts_json = request.is_json or "application/json" in request.headers.get("Accept", "")
    if accepts_json:
        return jsonify({"message": "That request expired. Refresh the page and try again."}), 400
    abort(400, description="That form expired. Refresh the page and try again.")


def protect_csrf():
    if request.method in SAFE_METHODS or request.endpoint == "health":
        return None
    expected = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "") or request.headers.get("X-CSRFToken", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        return _csrf_failure()
    return None

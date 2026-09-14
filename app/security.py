import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlparse

from flask import abort, current_app, g, jsonify, render_template, request, session

from app.db import (
    clear_rate_limit,
    get_rate_limit,
    log_security_event,
    record_rate_limit_failure,
)


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def prepare_security_context():
    g.csp_nonce = secrets.token_urlsafe(18)


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def rotate_csrf_token():
    session.pop("csrf_token", None)
    return get_csrf_token()


def _csrf_failure():
    accepts_json = request.is_json or "application/json" in request.headers.get("Accept", "")
    if accepts_json:
        return jsonify({"message": "That request expired. Refresh the page and try again."}), 400
    abort(400, description="That form expired. Refresh the page and try again.")


def protect_csrf():
    if request.method in SAFE_METHODS or request.endpoint == "health":
        return None

    # Browsers normally send Origin on state-changing requests. When present,
    # require it to match the externally visible request origin in addition to
    # the per-session CSRF token.
    origin = request.headers.get("Origin", "").strip()
    if origin:
        parsed = urlparse(origin)
        expected = urlparse(request.host_url)
        if parsed.scheme != expected.scheme or parsed.netloc.casefold() != expected.netloc.casefold():
            return _csrf_failure()

    expected = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "") or request.headers.get("X-CSRFToken", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        return _csrf_failure()
    return None


def security_hash(value):
    value = str(value or "").strip().casefold().encode("utf-8")
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(secret, value, hashlib.sha256).hexdigest()


def client_ip():
    return request.remote_addr or "unknown"


def limit_policy(scope, subject, max_attempts, window_seconds):
    subject = str(subject or "").strip().casefold()
    material = f"{scope}|{client_ip()}|{subject}"
    return {
        "key": f"{scope}:{security_hash(material)}",
        "scope": scope,
        "max_attempts": int(max_attempts),
        "window_seconds": int(window_seconds),
    }


def enforce_rate_limits(*policies):
    retry_after = 0
    blocked_scope = ""
    for policy in policies:
        state = get_rate_limit(policy["key"], policy["window_seconds"])
        if state["attempts"] >= policy["max_attempts"]:
            retry_after = max(retry_after, state["retry_after"])
            blocked_scope = policy["scope"]
    if not retry_after:
        return None

    audit_security_event("rate_limited", blocked_scope, {"retry_after": retry_after})
    message = "Too many attempts. Wait a little while and try again."
    if request.is_json or "application/json" in request.headers.get("Accept", ""):
        response = jsonify({"message": message, "retry_after": retry_after})
        response.status_code = 429
    else:
        response = current_app.make_response((render_template("errors/429.html", retry_after=retry_after), 429))
    response.headers["Retry-After"] = str(retry_after)
    return response


def record_rate_limit_failures(*policies):
    for policy in policies:
        record_rate_limit_failure(policy["key"], policy["window_seconds"])


def clear_rate_limits(*policies):
    for policy in policies:
        clear_rate_limit(policy["key"])


def audit_security_event(event_type, subject="", metadata=None):
    try:
        log_security_event(
            event_type,
            subject_hash=security_hash(subject) if subject else "",
            ip_hash=security_hash(client_ip()),
            metadata=metadata or {},
        )
    except Exception:
        current_app.logger.exception("Unable to persist security audit event")


def admin_session_fingerprint():
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    admin_password = current_app.config["CREW_ADMIN_PASSWORD"].encode("utf-8")
    totp_secret = current_app.config.get("CREW_ADMIN_TOTP_SECRET", "").encode("utf-8")
    return hmac.new(secret, b"admin-session:" + admin_password + b":" + totp_secret, hashlib.sha256).hexdigest()


def verify_totp(secret, code, now=None, window=1):
    """Verify a standard RFC 6238 six-digit TOTP without another runtime dependency."""
    secret = (secret or "").strip().replace(" ", "").upper()
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if not secret or len(code) != 6:
        return False
    try:
        padded = secret + "=" * ((8 - len(secret) % 8) % 8)
        key = base64.b32decode(padded, casefold=True)
    except Exception:
        return False
    counter = int((now or time.time()) // 30)
    for offset in range(-int(window), int(window) + 1):
        digest = hmac.new(key, struct.pack(">Q", counter + offset), hashlib.sha1).digest()
        dynamic_offset = digest[-1] & 0x0F
        binary = struct.unpack(">I", digest[dynamic_offset:dynamic_offset + 4])[0] & 0x7FFFFFFF
        expected = f"{binary % 1_000_000:06d}"
        if hmac.compare_digest(expected, code):
            return True
    return False


def totp_provisioning_uri(secret, account="CREW Admin", issuer="CREW"):
    return (
        f"otpauth://totp/{quote(issuer)}:{quote(account)}"
        f"?secret={quote(secret)}&issuer={quote(issuer)}&digits=6&period=30"
    )


def content_security_policy():
    nonce = getattr(g, "csp_nonce", "")
    directives = [
        "default-src 'self'",
        f"script-src 'self' 'nonce-{nonce}'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com data:",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "frame-src 'none'",
        "manifest-src 'self'",
    ]
    if current_app.config.get("IS_PRODUCTION"):
        directives.append("upgrade-insecure-requests")
    return "; ".join(directives)

import base64
import logging
import secrets
import sys

import click
from flask import Flask, g, jsonify, render_template, request
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

from config import Config
from . import db
from .security import (
    content_security_policy,
    get_csrf_token,
    prepare_security_context,
    protect_csrf,
    totp_provisioning_uri,
)


def _configure_logging(app):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def create_app():
    Config.validate()
    app = Flask(__name__)
    app.config.from_object(Config)
    if app.config["IS_PRODUCTION"]:
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    _configure_logging(app)

    # CREW sits behind exactly one trusted Nginx reverse proxy on the VPS.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)

    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .mystery.routes import mystery_bp
    from .trivia.routes import trivia_bp
    from .word.routes import word_bp
    from .tick_tock.routes import tick_tock_bp
    from .admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(mystery_bp)
    app.register_blueprint(trivia_bp)
    app.register_blueprint(word_bp)
    app.register_blueprint(tick_tock_bp)
    app.register_blueprint(admin_bp)

    app.before_request(prepare_security_context)
    app.before_request(protect_csrf)
    app.context_processor(lambda: {
        "csrf_token": get_csrf_token(),
        "csp_nonce": getattr(g, "csp_nonce", ""),
    })

    @app.get("/health", endpoint="health")
    def health():
        try:
            db.ping_db()
        except Exception:
            app.logger.exception("Database health check failed")
            return jsonify({"status": "unhealthy"}), 503
        return jsonify({"status": "ok"})

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", content_security_policy())
        if app.config["IS_PRODUCTION"]:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        # Authentication/admin/account responses should never be retained by a shared cache.
        if request.path.startswith(("/login", "/create-profile", "/recover", "/recovery-code", "/profile", "/admin")):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.cli.command("generate-admin-totp")
    def generate_admin_totp_command():
        """Generate a TOTP secret that can be added to a password manager/authenticator."""
        secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
        click.echo(f"CREW_ADMIN_TOTP_SECRET={secret}")
        click.echo(totp_provisioning_uri(secret))
        click.echo("Store the secret securely. Do not commit it to Git.")

    @app.errorhandler(400)
    def bad_request(_error):
        return render_template("errors/400.html"), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def too_many_requests(error):
        return render_template("errors/429.html", retry_after=getattr(error, "retry_after", None)), 429

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unhandled application error", exc_info=error)
        return render_template("errors/500.html"), 500

    return app

import base64
import secrets

import click
from flask import Flask, g, jsonify, render_template, request
from dotenv import load_dotenv
from werkzeug.exceptions import BadHost, SecurityError
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

from config import Config
from . import db
from .observability import init_observability
from .security import (
    content_security_policy,
    get_csrf_token,
    prepare_security_context,
    protect_csrf,
    totp_provisioning_uri,
)


def create_app():
    Config.validate()
    app = Flask(__name__)
    app.config.from_object(Config)
    if app.config["IS_PRODUCTION"]:
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    init_observability(app)

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

    def _database_ready():
        try:
            db.ping_db()
            return True
        except Exception:
            app.logger.exception("Database readiness check failed")
            return False

    @app.get("/health", endpoint="health")
    def health():
        # Preserve the v11 response contract used by existing deployment checks.
        if not _database_ready():
            return jsonify({"status": "unhealthy"}), 503
        return jsonify({"status": "ok"})

    @app.get("/health/live", endpoint="health_live")
    def health_live():
        return jsonify({"status": "ok", "version": app.config["APP_VERSION"]})

    @app.get("/health/ready", endpoint="health_ready")
    def health_ready():
        if not _database_ready():
            return jsonify({"status": "unhealthy", "version": app.config["APP_VERSION"]}), 503
        return jsonify({"status": "ok", "version": app.config["APP_VERSION"]})

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

    # Host validation can fail before Flask creates a URL adapter. Error pages that
    # extend base.html call url_for(), which is unavailable in that state, so keep
    # host-validation failures deliberately minimal and dependency-free.
    @app.errorhandler(SecurityError)
    @app.errorhandler(BadHost)
    def invalid_host(_error):
        return "Bad Request", 400, {"Content-Type": "text/plain; charset=utf-8"}

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

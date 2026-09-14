from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone

from flask import g, has_request_context, request

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
_STANDARD_LOG_ATTRS = set(logging.makeLogRecord({}).__dict__) | {
    "message", "asctime", "request_id"
}


class JsonFormatter(logging.Formatter):
    """Single-line JSON logs suitable for journald ingestion and alert pipelines."""

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", "")
        if request_id:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _STANDARD_LOG_ATTRS:
                continue
            if key in {
                "args", "created", "exc_info", "exc_text", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated", "stack_info",
                "thread", "threadName", "taskName",
            }:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            record.request_id = getattr(g, "request_id", "")
        else:
            record.request_id = ""
        return True


def _request_id():
    supplied = request.headers.get("X-Request-ID", "").strip()
    if _REQUEST_ID_RE.fullmatch(supplied):
        return supplied
    return uuid.uuid4().hex


def init_observability(app):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False

    @app.before_request
    def begin_request_observation():
        g.request_id = _request_id()
        g.request_started = time.perf_counter()

    @app.after_request
    def complete_request_observation(response):
        request_id = getattr(g, "request_id", "") or uuid.uuid4().hex
        response.headers.setdefault("X-Request-ID", request_id)
        started = getattr(g, "request_started", None)
        duration_ms = round((time.perf_counter() - started) * 1000, 2) if started else None
        # Health checks are frequent; only log unhealthy readiness probes.
        if not request.path.startswith("/health") or response.status_code >= 400:
            app.logger.info(
                "request.completed",
                extra={
                    "event": "request.completed",
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        return response


from collections.abc import Mapping
from datetime import date, datetime
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from flask import render_template


_REACT_ASSET_DIR = Path(__file__).resolve().parent / "static" / "react"


def json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


@lru_cache(maxsize=8)
def _react_asset_digest(filename, mtime_ns, size):
    path = _REACT_ASSET_DIR / filename
    return sha256(path.read_bytes()).hexdigest()[:12]


def react_asset_version(filename):
    path = _REACT_ASSET_DIR / filename
    try:
        stat = path.stat()
        return _react_asset_digest(filename, stat.st_mtime_ns, stat.st_size)
    except OSError:
        return "missing"


def render_player(page, title, body_class, payload, user, nav_points=None):
    data = json_safe(payload)
    data["shell"] = {
        "user": {
            "username": user.get("username", ""),
            "avatar": user.get("avatar", ""),
            "role": user.get("role", "player"),
        },
        "navPoints": nav_points,
        "active": "games" if page in {"mystery", "trivia", "word", "tick_tock"} else page,
    }
    return render_template(
        "player_app.html",
        react_page=page,
        react_title=title,
        react_body_class=body_class,
        react_payload=data,
        react_js_version=react_asset_version("player.js"),
        react_css_version=react_asset_version("player.css"),
    )

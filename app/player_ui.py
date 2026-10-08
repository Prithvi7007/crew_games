from collections.abc import Mapping
from datetime import date, datetime

from flask import render_template


def json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


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
    )

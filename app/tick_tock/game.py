from app.db import get_game_content

TARGETS = (7.0, 8.5, 6.25, 9.0, 5.75, 7.75, 6.5, 8.0)


def get_timer_config(game_day):
    scheduled = get_game_content("tick_tock", game_day.isoformat(), published_only=True)
    if scheduled:
        try:
            target = float(scheduled["content"].get("target_seconds"))
        except (TypeError, ValueError):
            target = None
        if target is not None and 2.0 <= target <= 30.0:
            return {"target": target, "theme": scheduled["theme_label"]}
    return {"target": TARGETS[game_day.toordinal() % len(TARGETS)], "theme": ""}


def get_target(game_day):
    return get_timer_config(game_day)["target"]


def score_for_difference(difference):
    if difference <= 0.10:
        return 100
    if difference <= 0.25:
        return 90
    if difference <= 0.50:
        return 80
    if difference <= 1.00:
        return 60
    if difference <= 1.50:
        return 40
    if difference <= 2.50:
        return 20
    return 10

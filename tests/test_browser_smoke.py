"""Opt-in real Chromium UI tests; never touch production or live player records.

CI runs with CREW_BROWSER_TESTS=1 and playwright installed. The ordinary
Python suite skips these tests when browsers are not provisioned.
"""
import os
import threading

import pytest
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

from app.db import create_profile, update_profile_role

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def _browser_enabled():
    if os.environ.get("CREW_BROWSER_TESTS") != "1":
        pytest.skip("Chromium smoke tests run in the dedicated browser CI job")
    from playwright.sync_api import sync_playwright
    return sync_playwright


@pytest.fixture
def ui(app, _browser_enabled):
    with app.app_context():
        create_profile(
            "BrowserTester",
            generate_password_hash("browser-test-passphrase"),
            "⭐",
            generate_password_hash("browser-test-recovery"),
        )
        from app.db import get_profile_by_username
        p = get_profile_by_username("BrowserTester")
        update_profile_role(int(p["id"]), "owner")

    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with _browser_enabled() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        base_url = f"http://127.0.0.1:{server.server_port}"
        page.goto(base_url + "/login", wait_until="domcontentloaded")
        page.locator('input[name="username"]').fill("BrowserTester")
        page.locator('input[name="password"]').fill("browser-test-passphrase")
        page.locator('form:has(input[name="username"]) button[type="submit"]').click()
        page.wait_for_url("**/home", timeout=15000)
        yield page, base_url
        browser.close()
    server.shutdown()
    thread.join(timeout=5)


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_all_four_games_have_aligned_real_headers(ui, width, height):
    page, base_url = ui
    page.set_viewport_size({"width": width, "height": height})
    routes = [
        ("mystery", "2026-10-12", "Mystery Monday"),
        ("trivia", "2026-10-13", "Trivia Tuesday"),
        ("word", "2026-10-14", "Wordle Wednesday"),
        ("tick-tock", "2026-10-15", "Tick-Tock Thursday"),
    ]
    observed = []
    for route, day, title in routes:
        page.goto(f"{base_url}/{route}?date={day}", wait_until="domcontentloaded")
        h = page.locator(".crew-game-heading h1")
        h.wait_for(timeout=12000)
        assert h.inner_text() == title
        heading = page.locator(".crew-game-heading")
        box = heading.bounding_box()
        assert box is not None
        assert box["x"] >= 0
        assert box["width"] > 0
        assert box["x"] + box["width"] <= width + 1
        observed.append((round(box["y"]), round(h.evaluate("(el) => parseFloat(getComputedStyle(el).fontSize)"))))
    assert max(a for a, _ in observed) - min(a for a, _ in observed) <= 10, observed
    assert max(b for _, b in observed) - min(b for _, b in observed) <= 2, observed


@pytest.mark.parametrize("route,heading", [
    ("/home", "Season"),
    ("/games", "Games"),
    ("/leaderboard", "Rankings"),
    ("/profile", "BrowserTester"),
    ("/trophies?trophy_tour_preview=1", "All badges"),
])
def test_authenticated_core_pages_render_without_overflow(ui, route, heading):
    page, base_url = ui
    page.goto(base_url + route, wait_until="domcontentloaded")
    page.locator("h1").first.wait_for(timeout=12000)
    assert heading.casefold() in page.locator("h1").first.inner_text().casefold()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")


def test_trivia_answer_advances_in_real_browser(ui):
    page, base_url = ui
    page.goto(base_url + "/trivia?date=2026-10-13", wait_until="domcontentloaded")
    page.locator(".crew-game-heading h1").wait_for(timeout=12000)
    # Answer by interacting with the real UI, not calling a test client route.
    page.locator(".react-trivia-option").first.click()
    page.locator(".react-trivia-feedback.is-visible").wait_for(timeout=12000)
    assert page.get_by_role("button", name="Next question").count() == 1


def test_mystery_reveal_updates_live_clue_count(ui):
    page, base_url = ui
    page.goto(base_url + "/mystery?date=2026-10-12", wait_until="domcontentloaded")
    page.locator(".crew-game-heading h1").wait_for(timeout=12000)
    assert "Clue 1 of 4" in page.locator(".stage-top").inner_text()
    page.get_by_role("button", name="Reveal another clue").click()
    page.get_by_text("Clue 2 of 4").wait_for(timeout=12000)
    assert page.locator(".clue-card").count() == 2


def test_word_keyboard_submits_a_real_guess(ui):
    page, base_url = ui
    page.goto(base_url + "/word?date=2026-10-14", wait_until="domcontentloaded")
    page.locator(".crew-game-heading h1").wait_for(timeout=12000)
    for letter in "MAGIC":
        page.locator(".word-keyboard").get_by_role("button", name=letter, exact=True).click()
    page.locator(".word-keyboard").get_by_role("button", name="ENTER").click()
    page.wait_for_function(
        "() => document.querySelector('.word-attempt-label')?.textContent.includes('1 / 6')"
        " || document.querySelector('.crew-result-score') !== null",
        timeout=15000,
    )


def test_tick_tock_start_and_stop_round_in_browser(ui):
    page, base_url = ui
    page.goto(base_url + "/tick-tock?date=2026-10-15", wait_until="domcontentloaded")
    page.locator(".crew-game-heading h1").wait_for(timeout=12000)
    page.get_by_role("button", name="Begin round").click()
    stop_button = page.get_by_role("button", name="STOP")
    stop_button.wait_for(timeout=12000)
    stop_button.click()
    page.get_by_text("TIME LOCKED", exact=True).wait_for(timeout=15000)


@pytest.mark.parametrize("viewport,reduced_motion", [
    ({"width": 1440, "height": 900}, False),
    ({"width": 390, "height": 844}, False),
    ({"width": 320, "height": 568}, False),
    ({"width": 844, "height": 390}, False),
    ({"width": 390, "height": 844}, True),
])
def test_real_badge_unlock_handoff_and_results_return(ui, app, monkeypatch, viewport, reduced_motion):
    """Complete an archive game in isolated SQLite; verify the whole cinematic handoff."""
    from app.mystery import routes as mystery_routes

    monkeypatch.setattr(
        mystery_routes, "get_puzzle",
        lambda day: {"theme": "Cinema test", "answer": "Cinema", "clues": ["a", "b", "c", "d"]},
    )
    monkeypatch.setattr(
        mystery_routes, "is_correct_answer",
        lambda answer, puzzle: answer.casefold() == puzzle["answer"].casefold(),
    )
    page, base_url = ui
    page.set_viewport_size(viewport)
    page.emulate_media(reduced_motion="reduce" if reduced_motion else "no-preference")
    page.goto(base_url + "/mystery?date=2026-09-21", wait_until="domcontentloaded")
    page.locator(".answer-entry input").fill("Cinema")
    page.get_by_role("button", name="Lock answer").click()

    if not reduced_motion:
        intro = page.locator(".cul-handoff-intro")
        intro.wait_for(timeout=12000)
        assert "ROUND COMPLETE" in intro.inner_text()

    cinema = page.get_by_role("dialog", name="New badges unlocked")
    cinema.wait_for(timeout=12000)
    assert page.locator(".cul-handoff-cinema").count() == 1
    assert "TRIPLE UNLOCK" in cinema.inner_text()
    # The live stage is full-bleed; it must not become a scrollable popup.
    layout = cinema.evaluate("""el => {
      const stage = el.getBoundingClientRect();
      const action = el.querySelector('.cul-cinema-footer button').getBoundingClientRect();
      const badges = el.querySelector('a.cul-view-badges').getBoundingClientRect();
      const heading = el.querySelector('.cul-message h2').getBoundingClientRect();
      return {
        width: stage.width, height: stage.height,
        overflow: getComputedStyle(el).overflowY,
        actionTop: action.top, actionBottom: action.bottom,
        badgesTop: badges.top, badgesBottom: badges.bottom,
        badgesLeft: badges.left, badgesRight: badges.right,
        headingTop: heading.top, headingBottom: heading.bottom
      };
    }""")
    assert abs(layout["width"] - viewport["width"]) < 2
    assert abs(layout["height"] - viewport["height"]) < 2
    assert layout["overflow"] == "hidden"
    assert 0 <= layout["actionTop"] < layout["actionBottom"] <= viewport["height"]
    assert 0 <= layout["badgesTop"] < layout["badgesBottom"] <= viewport["height"]
    assert 0 <= layout["badgesLeft"] < layout["badgesRight"] <= viewport["width"]
    assert cinema.get_by_role("link", name="View My Badges").get_attribute("href") == "/trophies"
    assert 0 <= layout["headingTop"] < layout["headingBottom"] <= viewport["height"]
    if reduced_motion:
        assert page.locator(".cul-handoff-intro").count() == 0

    cinema.get_by_role("button", name="View Results").click()
    page.locator(".cul-handoff").wait_for(state="detached", timeout=5000)
    assert "100" in page.locator(".crew-result-score").inner_text()
    page.reload(wait_until="domcontentloaded")
    page.locator(".crew-result-score").wait_for(timeout=12000)
    assert page.locator(".cul-handoff").count() == 0


@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 900},
    {"width": 390, "height": 844},
])
def test_season_stamp_is_crisp_across_nav_profile_rankings_and_badges(ui, viewport):
    """Owner's harmless try-on uses the same season stamp in every player view."""
    page, base_url = ui
    page.set_viewport_size(viewport)
    page.goto(base_url + "/trophies", wait_until="domcontentloaded")
    tour = page.locator(".crew-tour-dialog")
    if tour.count():
        tour.get_by_role("button", name="Maybe later").click()

    # Staff try-on is private, changes no score and issues no new badge award.
    page.locator(".trophy-badge-card button").first.click()
    navigation = page.locator(".crew-nav-avatar .crew-equipped-season")
    navigation.wait_for(timeout=12000)

    def inspect_stamp(locator, minimum_font, minimum_width):
        locator.wait_for(timeout=12000)
        assert locator.inner_text().startswith("S")
        style = locator.evaluate("""el => ({
            font: parseFloat(getComputedStyle(el).fontSize),
            width: el.getBoundingClientRect().width,
            background: getComputedStyle(el).backgroundColor
        })""")
        assert style["font"] >= minimum_font
        assert style["width"] >= minimum_width
        assert style["background"] == "rgb(7, 19, 33)"

    inspect_stamp(navigation, 8, 16)
    page.goto(base_url + "/profile", wait_until="domcontentloaded")
    inspect_stamp(page.locator(".v20-profile-identity .crew-equipped-season"), 11, 27)
    inspect_stamp(page.locator(".crew-nav-avatar .crew-equipped-season"), 8, 16)

    page.goto(base_url + "/leaderboard", wait_until="domcontentloaded")
    inspect_stamp(page.locator(".rankings-player-medal .crew-equipped-season").first, 8, 16)
    inspect_stamp(page.locator(".crew-nav-avatar .crew-equipped-season"), 8, 16)
    menu_trigger = page.locator(".crew-nav-account .account-trigger")
    if menu_trigger.is_visible():
        menu_trigger.click()
        inspect_stamp(page.locator(".crew-menu-avatar .crew-equipped-season"), 8, 16)


@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 900},
    {"width": 390, "height": 844},
])
def test_admin_studio_calendar_and_trivia_navigator_in_chromium(ui, viewport):
    """Future Admin content views remain navigable without saving a game attempt."""
    page, base_url = ui
    page.set_viewport_size(viewport)
    page.goto(base_url + "/admin?week=2027-02-22", wait_until="domcontentloaded")
    progress = page.locator(".studio-readiness-progress")
    progress.wait_for(timeout=12000)
    assert progress.get_attribute("max") == "4"
    assert page.locator(".studio-schedule-card").count() == 4
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")

    page.goto(base_url + "/admin/game/trivia/2027-02-23", wait_until="domcontentloaded")
    links = page.locator(".studio-question-jump")
    assert links.count() == 10
    assert page.locator("[data-studio-question]").count() == 10

    links.nth(9).click()
    assert page.locator("#studio-question-10").evaluate(
        "(card) => card === document.activeElement"
    )
    assert links.nth(9).get_attribute("aria-current") == "location"

    # Live warnings are advisory: never hide the native required inputs.
    first = page.locator('input[name="q1_a"]').input_value()
    page.locator('input[name="q1_b"]').fill(first)
    assert "duplicate" in page.locator("#studio-question-1 .studio-question-note").inner_text().lower()
    assert page.locator('input[name="q10_prompt"]').is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")


@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 900},
    {"width": 390, "height": 844},
])
def test_admin_mystery_word_and_timer_editor_feedback_in_browser(ui, viewport):
    """Editor previews react locally and never create a player game attempt."""
    page, base_url = ui
    page.set_viewport_size(viewport)

    page.goto(base_url + "/admin/game/mystery/2027-02-22", wait_until="domcontentloaded")
    mystery = page.locator('[data-studio-editor="mystery"]')
    mystery.locator('[name="answer"]').fill("STARDUST")
    mystery.locator('[name="clue_1"]').fill("The answer is STARDUST")
    assert "contains the answer" in mystery.locator('[data-studio-clue="1"] [data-studio-clue-feedback]').inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")

    page.goto(base_url + "/admin/game/word/2027-02-24", wait_until="domcontentloaded")
    word = page.locator('[data-studio-editor="word"]')
    word.locator('[name="solution"]').fill("MOVIE")
    assert word.locator("[data-studio-tile]").all_inner_texts() == list("MOVIE")
    assert "ready" in word.locator("[data-studio-status]").inner_text().lower()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")

    page.goto(base_url + "/admin/game/tick_tock/2027-02-25", wait_until="domcontentloaded")
    clock = page.locator('[data-studio-editor="tick_tock"]')
    clock.locator('[name="target_seconds"]').fill("12.35")
    assert clock.locator("[data-studio-timer-label]").inner_text() == "12.35 SEC"
    assert clock.locator("[data-studio-timer-fill]").evaluate(
        "(el) => parseFloat(el.style.width) > 0"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
    assert page.get_by_role("button", name="Review & publish").is_visible()


@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 900},
    {"width": 390, "height": 844},
])
def test_admin_studio_shared_navigation_keeps_sections_reachable(ui, viewport):
    """All operations pages share one active navigation with no mobile overflow."""
    page, base_url = ui
    page.set_viewport_size(viewport)
    for route, section in [
        ("/admin", "Schedule"),
        ("/admin/players", "Players"),
        ("/admin/settings", "Settings"),
        ("/admin/game/mystery/2027-02-22", "Schedule"),
        ("/admin/preview/mystery/2027-02-22", "Schedule"),
        ("/admin/test/mystery/2027-02-22", "Schedule"),
    ]:
        page.goto(base_url + route, wait_until="domcontentloaded")
        nav = page.get_by_role("navigation", name="Studio sections")
        active = nav.locator('[aria-current="page"]')
        assert active.count() == 1
        assert active.inner_text() == section
        assert page.get_by_role("navigation", name="Admin Studio sections").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
    page.goto(base_url + "/admin/settings#studio-seasons", wait_until="domcontentloaded")
    assert page.locator("#studio-seasons").count() == 1
    assert page.locator("#studio-access").count() == 1
    page.get_by_role("navigation", name="Admin Studio sections").get_by_role("link", name="Players").click()
    page.wait_for_url("**/admin/players", timeout=12000)
    assert page.locator(".admin-player-directory").is_visible()


@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 900},
    {"width": 390, "height": 844},
])
def test_admin_badge_insights_directory_and_player_season_ui(ui, viewport):
    """Persisted badge insights stay accessible across desktop and mobile."""
    page, base_url = ui
    page.set_viewport_size(viewport)
    page.goto(base_url + "/admin/players", wait_until="domcontentloaded")
    page.locator(".admin-player-directory").wait_for(timeout=12000)
    assert page.locator("th").filter(has_text="Badges").count() == 1
    assert page.locator(".admin-directory-badges").count() >= 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")

    page.locator(".admin-player-identity").first.click()
    page.locator("#admin-badge-insights-title").wait_for(timeout=12000)
    assert page.locator(".admin-badge-game-row").count() == 4
    assert page.locator(".admin-badge-season-stats > div").count() == 4
    assert page.locator('select[name="season"] option').count() >= 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")


@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 900},
    {"width": 390, "height": 844},
])
def test_champion_animation_previews_use_real_titles_and_badges(ui, monkeypatch, viewport):
    from datetime import date

    monkeypatch.setattr("app.main.routes.crew_today", lambda: date(2026, 10, 30))
    page, base_url = ui
    page.set_viewport_size(viewport)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(
        base_url + "/rewind?preview=1&prototype=1&story=5&champion=all",
        wait_until="domcontentloaded",
    )
    selector = page.get_by_role("combobox", name="Champion animation preview")
    selector.wait_for(timeout=12000)
    assert selector.locator("option").count() == 7
    assert page.locator(".rc-part").inner_text() == "01 / 10"
    assert page.get_by_text("ANIMATION DEMO · NO AWARD GRANTED", exact=True).is_visible()
    assert page.get_by_role("heading", name="SEASON 01 CHAMPION", exact=True).count() == 0
    assert page.locator(".champion-insignia").count() == 0
    page.get_by_role("button", name="BEGIN YOUR REWIND").click()
    page.get_by_role("heading", name="SEASON 01 CHAMPION", exact=True).click()
    assert page.locator(".champion-name").inner_text() == "BrowserTester"
    page.keyboard.press("ArrowRight")
    page.locator(".champion-closeup").wait_for(timeout=12000)
    page.locator(".rc-frame").hover()
    page.get_by_role("button", name="THE STORY BEHIND THIS MOMENT").click()
    sheet = page.get_by_role("dialog", name="How this moment was calculated")
    assert "Animation preview only." in sheet.locator("small").inner_text()
    page.get_by_role("button", name="Close evidence").click()
    page.get_by_role("button", name="Previous chapter").click()
    page.locator(".champion-winner.is-still").wait_for(timeout=12000)
    assert page.locator(".champion-cover").count() == 0
    assert page.get_by_role("button", name="PLAY", exact=False).is_visible()
    assert page.locator(".champion-name").evaluate("el => getComputedStyle(el).opacity") == "1"

    for key, title, badge in (
        ("season", "SEASON 01 CHAMPION", "Season Champion"),
        ("trivia", "TRIVIA LEADER", "Season Trivia Master"),
        ("word", "WORDLE LEADER", "Season Wordle Master"),
        ("mystery", "MYSTERY LEADER", "Season Mystery Master"),
        ("tick_tock", "TICK-TOCK LEADER", "Season Tick-Tock Master"),
    ):
        selector.select_option(key)
        page.wait_for_url("**&champion=" + key)
        page.locator(".champion-cover").wait_for(timeout=12000)
        assert page.get_by_role("heading", name=title, exact=True).count() == 0
        assert page.locator(".champion-insignia").count() == 0
        box = selector.bounding_box()
        assert box and 0 <= box["x"] < box["x"] + box["width"] <= viewport["width"]
        page.get_by_role("button", name="BEGIN YOUR REWIND").click()
        heading = page.get_by_role("heading", name=title, exact=True)
        heading.wait_for(timeout=12000)
        assert page.locator(".champion-name").inner_text() == "BrowserTester"
        assert page.locator(".champion-winner").get_attribute("data-game") == key
        assert page.locator(".champion-insignia svg").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        page.locator(".rc-frame").hover()
        page.get_by_role("button", name="PAUSE", exact=False).click()
        assert page.locator(".champion-cover").count() == 0
        assert page.locator(".rc-start-wrap").count() == 0
        paused = page.locator(".champion-name").evaluate("el => [getComputedStyle(el).opacity, getComputedStyle(el).transform]")
        page.wait_for_timeout(300)
        assert page.locator(".champion-name").evaluate("el => [getComputedStyle(el).opacity, getComputedStyle(el).transform]") == paused
        page.get_by_role("button", name="PLAY", exact=False).click()
        heading.click()
        page.keyboard.press("ArrowRight")
        page.get_by_role("heading", name=badge, exact=True).wait_for(timeout=12000)
        assert page.locator(".champion-closeup .champion-insignia svg").is_visible()
        page.locator(".rc-frame").hover()
        page.get_by_role("button", name="PAUSE", exact=False).click()
        paused = page.locator(".champion-closeup .champion-insignia").evaluate("el => [getComputedStyle(el).opacity, getComputedStyle(el).transform]")
        page.wait_for_timeout(300)
        assert page.locator(".champion-closeup .champion-insignia").evaluate("el => [getComputedStyle(el).opacity, getComputedStyle(el).transform]") == paused
        assert page.locator(".rc-finale-actions").count() == 0
        page.get_by_role("button", name="PLAY", exact=False).click()
        assert page.get_by_text("ANIMATION DEMO · NO AWARD GRANTED", exact=True).is_visible()
        page.get_by_role("button", name="WATCH AGAIN").click()
        page.locator(".champion-cover").wait_for(timeout=12000)
        assert page.get_by_role("heading", name=title, exact=True).count() == 0
    assert errors == []


def test_champion_reduced_motion_does_not_skip_the_first_reveal(ui, monkeypatch):
    from datetime import date

    monkeypatch.setattr("app.main.routes.crew_today", lambda: date(2026, 10, 30))
    page, base_url = ui
    page.emulate_media(reduced_motion="reduce")
    page.goto(
        base_url + "/rewind?preview=1&prototype=1&story=5&champion=season",
        wait_until="domcontentloaded",
    )
    page.locator(".champion-cover").wait_for(timeout=12000)
    page.get_by_role("button", name="EXPLORE YOUR STORY").click()
    page.get_by_role("heading", name="SEASON 01 CHAMPION", exact=True).wait_for(timeout=12000)
    assert page.locator(".rc-part").inner_text() == "01 / 02"
    assert page.locator(".champion-winner.is-reduced").count() == 1
    assert page.locator(".champion-name").inner_text() == "BrowserTester"
    assert not page.locator(".champion-overture").is_visible()
    page.get_by_role("button", name="NEXT", exact=False).click()
    page.get_by_role("heading", name="Season Champion", exact=True).wait_for(timeout=12000)
    page.get_by_role("button", name="WATCH AGAIN").click()
    page.locator(".champion-cover").wait_for(timeout=12000)


def test_champion_paused_visit_can_replay_and_early_finish_holds_complete_badge(ui, monkeypatch):
    from datetime import date
    monkeypatch.setattr("app.main.routes.crew_today", lambda: date(2026, 10, 30))
    page, base_url = ui
    page.goto(base_url + "/rewind?preview=1&prototype=1&story=5&champion=all")
    page.get_by_role("button", name="BEGIN YOUR REWIND").click()
    page.locator(".champion-winner").wait_for()
    page.keyboard.press("Space")
    page.keyboard.press("ArrowRight")
    page.locator(".champion-closeup").wait_for()
    page.keyboard.press("Space")
    page.wait_for_timeout(400)
    assert page.locator(".rc-part").inner_text() == "02 / 10"
    page.get_by_role("combobox", name="Champion animation preview").select_option("season")
    page.get_by_role("button", name="BEGIN YOUR REWIND").click()
    page.locator(".champion-winner").wait_for()
    page.keyboard.press("ArrowRight")
    page.locator(".champion-closeup").wait_for()
    page.keyboard.press("ArrowRight")
    page.get_by_role("button", name="WATCH AGAIN").wait_for()
    page.wait_for_function("() => [...document.querySelectorAll('.champion-closeup .champion-insignia, .champion-badge-name')].every(el => getComputedStyle(el).opacity === '1')")


@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 900}, {"width": 390, "height": 844},
])
def test_combined_rewind_switches_players_and_preserves_full_story(ui, app, viewport):
    from app.db import finalize_game_stats, profile_user_key
    from unittest.mock import patch
    from datetime import date

    with app.app_context():
        other = create_profile(
            "CombinedBrowserPlayer", generate_password_hash("browser-test-passphrase"),
            "⭐", generate_password_hash("browser-test-recovery"),
        )
        finalize_game_stats(profile_user_key(other["id"]), "word", "2026-10-21", 80, True)
    page, base_url = ui
    page.set_viewport_size(viewport)
    page.emulate_media(reduced_motion="reduce")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    with patch("app.main.routes.crew_today", return_value=date(2026, 10, 30)):
        page.goto(base_url + "/rewind?preview=1&prototype=1&story=5&combined=1")
        player_select = page.get_by_role("combobox", name="Preview player", exact=True)
        player_select.select_option("CombinedBrowserPlayer")
        page.wait_for_url("**/*player=CombinedBrowserPlayer")
        page.get_by_role("checkbox", name="Combine championship preview with Rewind").check()
        assert page.get_by_role("combobox", name="Preview player", exact=True).input_value() == "CombinedBrowserPlayer"
        page.get_by_role("button", name="EXPLORE YOUR STORY").click()
        assert page.locator(".champion-name").inner_text() == "CombinedBrowserPlayer"
        # Results preview has two earned-in-preview leader openings (four scenes).
        for _ in range(4):
            page.get_by_role("button", name="Next chapter", exact=True).click()
        page.locator("main.rc-podium .saga-podium-weeks").wait_for(state="visible")
        assert page.get_by_role("combobox", name="Preview player", exact=True).is_visible()
        page.get_by_role("combobox", name="Champion animation preview", exact=True).select_option("all")
        page.wait_for_url("**/*champion=all")
        assert page.get_by_role("checkbox", name="Combine championship preview with Rewind").is_checked()
        assert page.get_by_role("button", name="EXPLORE YOUR STORY").is_visible()
        page.get_by_role("combobox", name="Preview player", exact=True).select_option("BrowserTester")
        page.wait_for_url("**/*player=BrowserTester*")
        assert page.get_by_role("combobox", name="Champion animation preview", exact=True).input_value() == "all"
        assert page.get_by_role("button", name="EXPLORE YOUR STORY").is_visible()
        controls = page.locator(".rc-preview-controls").bounding_box()
        assert controls["x"] >= 0
        assert controls["x"] + controls["width"] <= viewport["width"]
        assert not errors

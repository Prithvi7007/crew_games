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

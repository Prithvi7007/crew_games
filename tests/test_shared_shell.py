from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shared_shell_and_page_styles_have_explicit_ownership():
    base = (ROOT / 'app' / 'templates' / 'base.html').read_text(encoding='utf-8')

    v18 = 'css/v18-pages.css'
    shell = 'css/crew-shell.css'
    page_block = '{% block head %}'
    foundation = 'css/phase1-foundation.css'

    assert shell in base
    assert base.index(v18) < base.index(shell) < base.index(page_block) < base.index(foundation)
    assert 'css/v23-core-pages.css' not in base


def test_authenticated_templates_use_shared_shell_hook():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    template = (ROOT / "app/templates/player_app.html").read_text(encoding="utf-8")

    assert 'id="crew-player-root"' in template
    assert "function AppHeader" in source
    assert source.count("<AppHeader") >= 8

    for component in (
        "HomePage",
        "GamesPage",
        "RankingsPage",
        "ProfilePage",
        "MysteryPage",
        "TriviaPage",
        "WordPage",
        "TickTockPage",
    ):
        assert f"function {component}" in source

def test_shared_shell_owns_reusable_navigation_contract():
    css = (ROOT / 'app' / 'static' / 'css' / 'crew-shell.css').read_text(
        encoding='utf-8'
    )

    required = (
        '.crew-app-page .app-nav',
        '.crew-app-page .desktop-nav',
        '.crew-app-page .crew-nav-account .account-trigger',
        '.crew-app-page .mobile-bottom-nav',
        '--crew-safe-bottom',
        '--crew-control-min',
    )

    for token in required:
        assert token in css



def test_page_styles_do_not_override_primary_chrome():
    css_root = ROOT / 'app' / 'static' / 'css'
    for filename in ('home.css', 'games.css', 'rankings.css'):
        text = (css_root / filename).read_text(encoding='utf-8')
        assert '.app-nav' not in text, filename
        assert '.desktop-nav' not in text, filename
        assert '.mobile-bottom-nav' not in text, filename


def test_accessibility_foundation_no_longer_duplicates_mobile_shell():
    css = (ROOT / 'app' / 'static' / 'css' / 'phase1-foundation.css').read_text(
        encoding='utf-8'
    )
    assert '.mobile-bottom-nav.mobile-bottom-nav' not in css

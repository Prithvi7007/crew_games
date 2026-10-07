from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shared_shell_stylesheet_is_loaded_after_page_css():
    base = (ROOT / 'app' / 'templates' / 'base.html').read_text(encoding='utf-8')

    v18 = 'css/v18-pages.css'
    shell = 'css/crew-shell.css'
    foundation = 'css/phase1-foundation.css'

    assert shell in base
    assert base.index(v18) < base.index(shell) < base.index(foundation)


def test_authenticated_templates_use_shared_shell_hook():
    templates = (
        'home.html',
        'games.html',
        'leaderboard.html',
        'profile.html',
        'trivia.html',
        'mystery.html',
        'word.html',
        'tick_tock.html',
    )

    for name in templates:
        text = (ROOT / 'app' / 'templates' / name).read_text(encoding='utf-8')
        assert 'crew-app-page' in text, name


def test_shared_shell_owns_reusable_navigation_contract():
    css = (ROOT / 'app' / 'static' / 'css' / 'crew-shell.css').read_text(
        encoding='utf-8'
    )

    required = (
        '.crew-app-page .app-nav',
        '.crew-app-page .desktop-nav',
        '.crew-app-page .account-trigger',
        '.crew-app-page .mobile-bottom-nav',
        '--crew-safe-bottom',
        '--crew-control-min',
    )

    for token in required:
        assert token in css


def test_page_styles_no_longer_own_primary_chrome():
    checks = {
        'v18-pages.css': '.v14-games-page .app-nav',
        'v19-rankings.css': '.v19-rankings-page .app-nav',
        'v19-trivia.css': '.v19-trivia-page .app-nav',
        'v20-profile.css': '.v20-profile-page .app-nav',
    }

    css_root = ROOT / 'app' / 'static' / 'css'
    for filename, selector in checks.items():
        text = (css_root / filename).read_text(encoding='utf-8')
        assert selector not in text, filename

    today = (css_root / 'v17-today.css').read_text(encoding='utf-8')
    # Today keeps one tablet-only sizing override, but no longer owns the base/mobile chrome.
    assert today.count('.v17-today-page .app-nav') <= 1
    assert '.v17-today-page .mobile-bottom-nav' not in today


def test_accessibility_foundation_no_longer_duplicates_mobile_shell():
    css = (ROOT / 'app' / 'static' / 'css' / 'phase1-foundation.css').read_text(
        encoding='utf-8'
    )
    assert '.mobile-bottom-nav.mobile-bottom-nav' not in css

(() => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const nativeFetch = window.fetch.bind(window);
    let leaderboardRequestId = 0;

    function showRuntimeNotice(message) {
        let notice = document.querySelector('[data-crew-runtime-notice]');
        if (!notice) {
            notice = document.createElement('div');
            notice.className = 'crew-runtime-notice';
            notice.dataset.crewRuntimeNotice = '';
            notice.setAttribute('role', 'status');
            notice.setAttribute('aria-live', 'polite');
            document.body.append(notice);
        }
        notice.textContent = message;
        notice.hidden = false;
        window.clearTimeout(showRuntimeNotice.timer);
        showRuntimeNotice.timer = window.setTimeout(() => {
            notice.hidden = true;
        }, 5000);
    }

    function taggedError(message, key) {
        const error = new Error(message);
        error[key] = true;
        return error;
    }

    window.fetch = async (input, init = {}) => {
        const requestUrl = typeof input === 'string'
            ? new URL(input, window.location.href)
            : new URL(input.url, window.location.href);

        const method = String(
            init.method || (typeof input !== 'string' && input.method) || 'GET'
        ).toUpperCase();

        const sameOrigin = requestUrl.origin === window.location.origin;
        const isLeaderboard =
            sameOrigin &&
            method === 'GET' &&
            requestUrl.pathname === '/api/leaderboard';

        const requestId = isLeaderboard ? ++leaderboardRequestId : 0;

        if (sameOrigin && !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
            const headers = new Headers(
                init.headers || (typeof input !== 'string' ? input.headers : undefined)
            );
            if (csrfToken && !headers.has('X-CSRFToken')) {
                headers.set('X-CSRFToken', csrfToken);
            }
            init = { ...init, headers };
        }

        try {
            const response = await nativeFetch(input, init);

            // Flask redirects expired authenticated requests to /login.
            // Fetch follows that redirect automatically, which previously made
            // React try to parse the HTML login page as JSON.
            if (response.redirected && sameOrigin) {
                const redirectedUrl = new URL(response.url, window.location.href);
                if (
                    redirectedUrl.origin === window.location.origin &&
                    redirectedUrl.pathname === '/login'
                ) {
                    const next = `${window.location.pathname}${window.location.search}`;
                    window.location.assign(`/login?next=${encodeURIComponent(next)}`);
                    return new Promise(() => {});
                }
            }

            if (isLeaderboard) {
                // A slower response from an older filter selection must never
                // overwrite the player's newer selection.
                if (requestId !== leaderboardRequestId) {
                    throw taggedError(
                        'Stale leaderboard response.',
                        'crewLeaderboardStale'
                    );
                }

                if (!response.ok) {
                    throw taggedError(
                        "Couldn't refresh rankings.",
                        'crewLeaderboard'
                    );
                }
            }

            return response;
        } catch (error) {
            if (!isLeaderboard) throw error;

            if (
                requestId !== leaderboardRequestId ||
                error?.crewLeaderboardStale
            ) {
                throw taggedError(
                    'Stale leaderboard response.',
                    'crewLeaderboardStale'
                );
            }

            if (error?.crewLeaderboard) throw error;

            const wrapped = taggedError(
                "Couldn't refresh rankings.",
                'crewLeaderboard'
            );
            wrapped.cause = error;
            throw wrapped;
        }
    };

    window.addEventListener('unhandledrejection', (event) => {
        if (event.reason?.crewLeaderboardStale) {
            event.preventDefault();
            return;
        }

        if (event.reason?.crewLeaderboard) {
            event.preventDefault();
            showRuntimeNotice(
                "Couldn't refresh rankings. Your current results are still shown. Try again."
            );
        }
    });
})();

// Password reveal controls on CREW auth screens.
document.querySelectorAll('[data-password-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
        const input = document.getElementById(button.dataset.passwordToggle);
        if (!input) return;
        const showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        button.textContent = showing ? 'Show' : 'Hide';
        button.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
        input.focus({ preventScroll: true });
    });
});

// Global CREW account menu.
document.querySelectorAll('[data-account-menu]').forEach((menu) => {
    const trigger = menu.querySelector('[data-account-trigger]');
    const panel = menu.querySelector('[data-account-panel]');
    if (!trigger || !panel) return;

    const items = () => [...panel.querySelectorAll('[role="menuitem"]')];
    const setOpen = (open, { focusFirst = false, restoreFocus = false } = {}) => {
        panel.hidden = !open;
        trigger.setAttribute('aria-expanded', String(open));
        menu.classList.toggle('is-open', open);
        if (open && focusFirst) items()[0]?.focus();
        if (!open && restoreFocus) trigger.focus();
    };

    trigger.addEventListener('click', () => {
        setOpen(panel.hidden);
    });

    trigger.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setOpen(true, { focusFirst: true });
        }
    });

    panel.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            event.preventDefault();
            setOpen(false, { restoreFocus: true });
            return;
        }
        if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
        const menuItems = items();
        const current = menuItems.indexOf(document.activeElement);
        if (current < 0) return;
        event.preventDefault();
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        menuItems[(current + delta + menuItems.length) % menuItems.length]?.focus();
    });

    document.addEventListener('pointerdown', (event) => {
        if (!panel.hidden && !menu.contains(event.target)) setOpen(false);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !panel.hidden) setOpen(false, { restoreFocus: true });
    });
});

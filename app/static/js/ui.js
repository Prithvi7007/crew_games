(() => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const nativeFetch = window.fetch.bind(window);
    window.fetch = (input, init = {}) => {
        const requestUrl = typeof input === 'string' ? new URL(input, window.location.href) : new URL(input.url, window.location.href);
        const method = String(init.method || (typeof input !== 'string' && input.method) || 'GET').toUpperCase();
        if (requestUrl.origin === window.location.origin && !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
            const headers = new Headers(init.headers || (typeof input !== 'string' ? input.headers : undefined));
            if (csrfToken && !headers.has('X-CSRFToken')) headers.set('X-CSRFToken', csrfToken);
            init = { ...init, headers };
        }
        return nativeFetch(input, init);
    };
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

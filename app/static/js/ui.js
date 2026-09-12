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

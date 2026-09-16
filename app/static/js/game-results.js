(() => {
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function rankingsUrl() {
    const link = [...document.querySelectorAll('.desktop-nav a, .mobile-bottom-nav a')]
      .find((item) => /leaderboard|rankings/i.test(item.getAttribute('href') || '') || /rankings/i.test(item.textContent || ''));
    return link?.href || '/leaderboard';
  }

  function render(mount, options = {}) {
    if (!mount) return null;

    document.body.classList.add('crew-game-complete');

    const game = options.game || 'generic';
    const stage = el('section', `crew-result-stage crew-result-${game}`);
    stage.setAttribute('aria-live', 'polite');

    const shade = el('div', 'crew-result-shade');
    shade.setAttribute('aria-hidden', 'true');

    const content = el('div', 'crew-result-content');

    const burst = el('div', 'crew-result-burst');
    burst.setAttribute('aria-hidden', 'true');
    burst.append(el('span', '', options.icon || '✦'));

    const kicker = el('p', 'crew-result-kicker', options.kicker || 'ROUND COMPLETE');
    const score = el('strong', 'crew-result-score', options.score ?? 0);
    const label = el('span', 'crew-result-label', 'POINTS');

    content.append(burst, kicker, score, label);

    const metaValues = Array.isArray(options.meta) ? options.meta.filter(Boolean) : [];
    if (metaValues.length) {
      const meta = el('div', 'crew-result-meta');
      metaValues.forEach((value) => meta.append(el('span', '', value)));
      content.append(meta);
    }

    if (options.copy) {
      content.append(el('p', 'crew-result-copy', options.copy));
    }

    const actions = el('div', 'crew-result-actions');
    const rankings = el('a', 'crew-result-primary');
    rankings.href = options.rankingsUrl || rankingsUrl();
    rankings.append(el('span', '', 'View Rankings'), el('span', '', '→'));
    actions.append(rankings);
    content.append(actions);

    stage.append(shade, content);
    mount.replaceWith(stage);

    return stage;
  }

  window.CREWGameResult = { render };
})();

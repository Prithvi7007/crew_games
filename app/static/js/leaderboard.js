(() => {
  const root = document.querySelector('[data-leaderboard]');
  if (!root) return;

  const seasonSelect = document.getElementById('leader-season');
  const weekSelect = document.getElementById('leader-week');
  const list = document.getElementById('leader-list');
  const empty = document.getElementById('leader-empty');
  const tabs = [...document.querySelectorAll('[data-game-filter]')];
  const filters = JSON.parse(document.getElementById('leaderboard-filter-data').textContent);
  let state = JSON.parse(document.getElementById('leaderboard-initial').textContent);
  let game = tabs.find(tab => tab.classList.contains('active'))?.dataset.gameFilter || 'all';

  function makeRow(player) {
    const row = document.createElement('div');
    row.className = `rankings-leader-row place-${player.rank || 0}${player.me ? ' is-me' : ''}`;

    const rank = document.createElement('span');
    rank.className = 'rankings-rank';
    rank.textContent = player.rank || '—';

    const playerCell = document.createElement('span');
    playerCell.className = 'rankings-player';

    const avatar = document.createElement('i');
    avatar.textContent = String(player.avatar || '');
    avatar.setAttribute('aria-hidden', 'true');

    const meta = document.createElement('span');
    const name = document.createElement('strong');
    name.textContent = String(player.username || '');

    const detail = document.createElement('small');
    detail.textContent = String(player.detail || '');

    meta.append(name, detail);
    playerCell.append(avatar, meta);

    const points = document.createElement('strong');
    points.className = 'rankings-number';
    points.textContent = String(player.points || 0);

    const played = document.createElement('span');
    played.className = 'rankings-number';
    played.textContent = String(player.completed || 0);

    const average = document.createElement('span');
    average.className = 'rankings-number';
    average.textContent = player.completed
      ? (player.points / player.completed).toFixed(1)
      : '—';

    const streak = document.createElement('span');
    streak.className = 'rankings-streak';
    streak.textContent = player.streak ? `🔥 ${player.streak}` : '—';

    row.append(rank, playerCell, points, played, average, streak);
    return row;
  }

  function render() {
    empty.hidden = state.players.length > 0;
    list.replaceChildren(...state.players.map(makeRow));
  }

  function selectedSeason() {
    return filters.seasons.find(item => String(item.id) === seasonSelect.value);
  }

  function rebuildWeeks() {
    const selected = selectedSeason();
    const previous = weekSelect.value;
    weekSelect.replaceChildren(new Option('All Weeks', 'all'));

    for (let n = 1; n <= (selected?.weeks_total || 1); n += 1) {
      weekSelect.add(new Option(`Week ${String(n).padStart(2, '0')}`, String(n)));
    }

    weekSelect.value = [...weekSelect.options].some(option => option.value === previous)
      ? previous
      : 'all';
  }

  async function load() {
    const params = new URLSearchParams({
      season: seasonSelect.value,
      week: weekSelect.value,
      game,
    });

    const response = await fetch(`${root.dataset.apiUrl}?${params}`, {
      headers: {'Accept': 'application/json'},
    });
    if (!response.ok) return;

    state = await response.json();
    history.replaceState(null, '', `/leaderboard?${params}`);
    render();
  }

  seasonSelect.addEventListener('change', () => {
    rebuildWeeks();
    load();
  });

  weekSelect.addEventListener('change', load);

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      game = tab.dataset.gameFilter;
      tabs.forEach(item => {
        const active = item === tab;
        item.classList.toggle('active', active);
        item.setAttribute('aria-pressed', String(active));
      });
      load();
    });
  });

  render();
})();

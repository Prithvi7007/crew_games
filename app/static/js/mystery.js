(() => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const root = document.querySelector('[data-mystery]'); if (!root) return;
  let state = JSON.parse(document.getElementById('mystery-state').textContent);
  const clues = document.getElementById('clue-list'), points = document.getElementById('mystery-points'), count = document.getElementById('clue-count');
  const form = document.getElementById('mystery-form'), input = document.getElementById('mystery-answer'), reveal = document.getElementById('reveal-clue'), message = document.getElementById('mystery-message');
  const submit = form.querySelector('button');
  const pointsLabel = points.nextElementSibling;
  const statIcon = root.querySelector('.stat-icon');

  function renderClues() {
    clues.replaceChildren(...state.clues.map((clue, index) => {
      const article = document.createElement('article'); article.className = 'clue-card';
      const number = document.createElement('span'); number.textContent = String(index + 1).padStart(2, '0');
      const text = document.createElement('p'); text.textContent = String(clue ?? '');
      article.append(number, text);
      return article;
    }));
  }

  function renderCompleteState() {
    const mount = root.querySelector('.game-two-column');
    if (!mount || !window.CREWGameResult) return;

    window.CREWGameResult.render(mount, {
      game: 'mystery',
      icon: state.won ? '✓' : '◇',
      kicker: state.won ? 'CASE CLOSED' : 'CASE COMPLETE',
      score: state.score,
      meta: state.won
        ? [`SOLVED ON CLUE ${state.revealed_count}`, String(state.answer || '').toUpperCase()]
        : [`ANSWER · ${String(state.answer || '').toUpperCase()}`],
      copy: 'Monday is in the books.'
    });
  }

  function render(){
    renderClues();

    const done = Boolean(state.completed);
    const locked = done || !state.playable;
    const noMoreClues = state.revealed_count >= state.total_clues;

    root.classList.toggle('is-complete', done);
    points.textContent = done ? state.score : state.potential_score;

    if (pointsLabel) pointsLabel.textContent = done ? 'points earned' : 'points available';
    if (statIcon) statIcon.textContent = done ? '✓' : '?';

    count.textContent = done
      ? (state.won ? `Solved on clue ${state.revealed_count}` : 'Mystery complete')
      : `Clue ${state.revealed_count} of ${state.total_clues}`;

    input.disabled = locked;
    submit.disabled = locked;
    reveal.disabled = locked || noMoreClues;

    // Completed/upcoming states should not leave dead controls on screen.
    form.hidden = done || !state.playable;
    reveal.hidden = done || !state.playable || noMoreClues;

    if (!state.playable && !done) {
      message.className = 'archive-play-banner upcoming';
      message.replaceChildren();
      const strong = document.createElement('strong');
      const detail = document.createElement('span');
      strong.textContent = 'Coming soon';
      detail.textContent = 'This challenge has not opened yet.';
      message.append(strong, detail);
    } else if (done) {
      renderCompleteState();
    }
  }

  async function post(url, body){
    const r = await fetch(url,{
      method:'POST',
      headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':csrfToken},
      body:body ? JSON.stringify(body) : null
    });
    const d = await r.json();
    if(!r.ok) throw new Error(d.message || 'Try again.');
    return d;
  }

  form.addEventListener('submit', async e=>{
    e.preventDefault();
    if(!input.value.trim()) return;
    message.className = 'game-message neutral';
    message.textContent = 'Checking…';
    try {
      const d = await post(root.dataset.guessUrl,{answer:input.value});
      state = d.state;
      input.value = '';
      message.className = `game-message ${d.correct ? 'success' : 'error'}`;
      message.textContent = d.message;
      render();
    } catch(err) {
      message.className = 'game-message error';
      message.textContent = err.message;
    }
  });

  reveal.addEventListener('click', async()=>{
    try {
      const d = await post(root.dataset.revealUrl);
      state = d.state;
      message.className = 'game-message neutral';
      message.textContent = 'Another clue unlocked.';
      render();
    } catch(err) {
      message.className = 'game-message error';
      message.textContent = err.message;
    }
  });

  render();
})();

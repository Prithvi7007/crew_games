(() => {
  const mount = document.getElementById('v2-test-app');
  const node = document.getElementById('v2-test-payload');
  if (!mount || !node) return;

  const payload = JSON.parse(node.textContent || '{}');
  const reset = document.querySelector('[data-v2-test-reset]');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const normalize = value => String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '');

  function mystery() {
    const content = payload.content || {};
    const clues = Array.isArray(content.clues) ? content.clues : [];
    const accepted = new Set([content.answer, ...(content.accepted || [])].map(normalize));
    const scores = [100, 75, 50, 25];
    let index = 0;

    function render(message='') {
      mount.innerHTML = `
        <div class="v2-test-kicker">${esc(payload.theme || 'Mystery Monday')}</div>
        <div class="v2-test-score"><strong>${scores[index] ?? 0}</strong><span>PTS AVAILABLE</span></div>
        <h2>Clue ${Math.min(index + 1, clues.length)} of ${clues.length}</h2>
        <div class="v2-test-clues">${clues.slice(0, index + 1).map((clue, i) => `<article><span>${String(i+1).padStart(2,'0')}</span><p>${esc(clue)}</p></article>`).join('')}</div>
        <form class="v2-test-answer"><input name="answer" autocomplete="off" placeholder="Your answer" required><button type="submit">Lock answer →</button></form>
        <p class="v2-test-message">${esc(message)}</p>
      `;
      mount.querySelector('form').addEventListener('submit', event => {
        event.preventDefault();
        const answer = new FormData(event.currentTarget).get('answer');
        if (accepted.has(normalize(answer))) {
          mount.innerHTML = `<div class="v2-test-result"><span>CASE CLOSED</span><strong>${scores[index] ?? 0}</strong><small>PTS · ${esc(content.answer)}</small><p>Test complete. Nothing was saved.</p></div>`;
          return;
        }
        if (index >= clues.length - 1) {
          mount.innerHTML = `<div class="v2-test-result"><span>CASE COMPLETE</span><strong>0</strong><small>PTS · ANSWER ${esc(content.answer)}</small><p>Test complete. Nothing was saved.</p></div>`;
          return;
        }
        index += 1;
        render('Not quite — another clue unlocked.');
      });
    }
    render();
  }

  function trivia() {
    const questions = (payload.content || {}).questions || [];
    let index = 0;
    let score = 0;

    function render(feedback='') {
      if (index >= questions.length) {
        mount.innerHTML = `<div class="v2-test-result"><span>ROUND COMPLETE</span><strong>${score}</strong><small>PTS · ${questions.length} QUESTIONS</small><p>Test complete. Nothing was saved.</p></div>`;
        return;
      }
      const q = questions[index];
      mount.innerHTML = `
        <div class="v2-test-kicker">${esc(payload.theme || 'Trivia Tuesday')}</div>
        <div class="v2-test-score"><strong>${score}</strong><span>TEST SCORE</span></div>
        <h2>${esc(q.prompt)}</h2>
        <div class="v2-test-options">${(q.options || []).map((option, i) => `<button type="button" data-choice="${i}"><b>${['A','B','C','D'][i]}</b><span>${esc(option)}</span></button>`).join('')}</div>
        <p class="v2-test-message">${esc(feedback || `Question ${index + 1} of ${questions.length}`)}</p>
      `;
      mount.querySelectorAll('[data-choice]').forEach(button => button.addEventListener('click', () => {
        const selected = Number(button.dataset.choice);
        const correct = selected === Number(q.answer);
        if (correct) score += 10;
        const correctText = q.options[Number(q.answer)];
        index += 1;
        render(correct ? 'Correct.' : `Not quite — ${correctText}.`);
      }));
    }
    render();
  }

  function evaluateWord(guess, solution) {
    const result = [...guess].map(letter => ({letter, state:'absent'}));
    const remaining = {};
    [...solution].forEach((letter, i) => {
      if (guess[i] === letter) result[i].state = 'correct';
      else remaining[letter] = (remaining[letter] || 0) + 1;
    });
    result.forEach(tile => {
      if (tile.state === 'correct') return;
      if ((remaining[tile.letter] || 0) > 0) {
        tile.state = 'present';
        remaining[tile.letter] -= 1;
      }
    });
    return result;
  }

  function word() {
    const solution = String((payload.content || {}).solution || '').toUpperCase();
    const scores = [100,80,65,50,40,30];
    let guesses = [];

    function render(message='') {
      const won = guesses.includes(solution);
      const done = won || guesses.length >= 6;
      if (done) {
        const score = won ? scores[guesses.length - 1] : 10;
        mount.innerHTML = `<div class="v2-test-result"><span>${won ? 'WORD SOLVED' : 'ROUND COMPLETE'}</span><strong>${score}</strong><small>PTS · ${esc(solution)}</small><p>Test complete. Nothing was saved.</p></div>`;
        return;
      }
      mount.innerHTML = `
        <div class="v2-test-kicker">${esc(payload.theme || 'Wordle Wednesday')}</div>
        <div class="v2-test-score"><strong>${scores[guesses.length]}</strong><span>PTS AVAILABLE</span></div>
        <h2>Guess the five-letter word.</h2>
        <div class="v2-test-word-board">${guesses.map(guess => `<div>${evaluateWord(guess, solution).map(tile => `<i class="${tile.state}">${tile.letter}</i>`).join('')}</div>`).join('')}</div>
        <form class="v2-test-answer"><input name="guess" maxlength="5" autocomplete="off" placeholder="Five letters" required><button type="submit">Submit guess →</button></form>
        <p class="v2-test-message">${esc(message || `${guesses.length} / 6 guesses`)}</p>
      `;
      mount.querySelector('form').addEventListener('submit', event => {
        event.preventDefault();
        const guess = String(new FormData(event.currentTarget).get('guess') || '').trim().toUpperCase();
        if (!/^[A-Z]{5}$/.test(guess)) return render('Use exactly five letters.');
        guesses.push(guess);
        render(guess === solution ? 'Correct.' : 'Keep going.');
      });
    }
    render();
  }

  function timerScore(diff) {
    if (diff <= .10) return 100;
    if (diff <= .25) return 90;
    if (diff <= .50) return 80;
    if (diff <= 1) return 60;
    if (diff <= 1.5) return 40;
    if (diff <= 2.5) return 20;
    return 10;
  }

  function timer() {
    const target = Number((payload.content || {}).target_seconds || 7);
    let started = null;
    mount.innerHTML = `
      <div class="v2-test-kicker">${esc(payload.theme || 'Tick-Tock Thursday')}</div>
      <h2>Your target</h2>
      <div class="v2-test-target">${target.toFixed(2)}<small>SEC</small></div>
      <button class="v2-test-timer-button" type="button">Begin round</button>
      <p class="v2-test-message">The timer will disappear once the test begins.</p>
    `;
    const button = mount.querySelector('button');
    const message = mount.querySelector('.v2-test-message');
    button.addEventListener('click', () => {
      if (!started) {
        started = performance.now();
        button.textContent = 'STOP';
        message.textContent = 'Timer hidden. Stop when your internal clock says it is time.';
        return;
      }
      const elapsed = (performance.now() - started) / 1000;
      const signed = elapsed - target;
      const diff = Math.abs(signed);
      mount.innerHTML = `<div class="v2-test-result"><span>TIME LOCKED</span><strong>${timerScore(diff)}</strong><small>PTS · ${elapsed.toFixed(2)} SEC · ${diff.toFixed(2)} SEC ${signed >= 0 ? 'LATE' : 'EARLY'}</small><p>Test complete. Nothing was saved.</p></div>`;
    });
  }

  function boot() {
    if (payload.game_key === 'mystery') mystery();
    else if (payload.game_key === 'trivia') trivia();
    else if (payload.game_key === 'word') word();
    else if (payload.game_key === 'tick_tock') timer();
    else mount.textContent = 'Unsupported test game.';
  }

  reset?.addEventListener('click', boot);
  boot();
})();

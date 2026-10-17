/* CREW Studio v23: advisory previews for Mystery, Wordle and Tick-Tock.
   No submissions, network calls, value mutations, or player-state interaction. */
(() => {
  'use strict';
  const editor = document.querySelector('[data-studio-editor]');
  if (!editor) return;
  const game = editor.dataset.studioEditor;
  const locked = editor.dataset.studioLocked === 'true';
  const status = editor.querySelector('[data-studio-status]');
  const normalize = (text) => String(text || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase();

  const notify = (message, state) => {
    if (!status) return;
    if (status.textContent !== message) status.textContent = message;
    status.dataset.state = state;
  };

  function updateMystery() {
    const answer = normalize(editor.querySelector('[name="answer"]')?.value);
    const clues = [...editor.querySelectorAll('[data-studio-clue]')];
    const texts = clues.map((clue) => normalize(clue.querySelector('textarea')?.value));
    let duplicates = 0;
    let spoilers = 0;
    clues.forEach((clue, index) => {
      const text = texts[index];
      const repeated = Boolean(text) && texts.indexOf(text) !== index;
      const spoiler = Boolean(text && answer.length >= 4 && text.includes(answer));
      const warning = repeated || spoiler;
      if (repeated) duplicates += 1;
      if (spoiler) spoilers += 1;
      const note = clue.querySelector('[data-studio-clue-feedback]');
      const original = clue.querySelector('textarea')?.value || '';
      if (note) {
        note.dataset.state = warning ? 'warning' : text ? 'ready' : 'incomplete';
        note.textContent = locked ? 'Read-only: this date is locked.'
          : repeated ? 'This clue repeats an earlier clue.'
          : spoiler ? 'This clue contains the answer. Consider a subtler hint.'
          : text ? `${original.length} / 280 characters · Editorial review recommended`
          : 'Add a clue to complete this stage.';
      }
    });
    const filled = texts.filter(Boolean).length;
    notify(locked ? 'Content locked · read-only' :
      `${filled} / 4 clues written${duplicates || spoilers ? ' · possible spoilers or repeats' : ''}`,
      duplicates || spoilers ? 'warning' : filled === 4 && answer ? 'ready' : 'incomplete');
  }

  function updateWord() {
    const word = (editor.querySelector('[name="solution"]')?.value || '').trim();
    const letters = [...word.toUpperCase()];
    editor.querySelectorAll('[data-studio-tile]').forEach((tile, index) => {
      const letter = letters[index];
      tile.textContent = letter || '·';
      tile.classList.toggle('is-filled', Boolean(letter));
    });
    const valid = /^[A-Za-z]{5}$/.test(word);
    notify(locked ? 'Content locked · read-only'
      : valid ? 'Five-letter solution ready for editorial review.'
      : `${Math.min(word.length, 5)} / 5 letters · Use A–Z only.`,
    valid ? 'ready' : 'incomplete');
  }

  function updateTimer() {
    const input = editor.querySelector('[name="target_seconds"]');
    const raw = (input?.value || '').trim();
    const seconds = Number(raw);
    const valid = raw !== '' && Number.isFinite(seconds) && seconds >= 2 && seconds <= 30
      && Math.abs(seconds * 100 - Math.round(seconds * 100)) < 1e-7;
    const preview = editor.querySelector('[data-studio-timer-label]');
    const fill = editor.querySelector('[data-studio-timer-fill]');
    if (preview) preview.textContent = valid ? `${seconds.toFixed(2)} SEC` : '—';
    if (fill) fill.style.width = valid ? `${((seconds - 2) / 28) * 100}%` : '0%';
    notify(locked ? 'Content locked · read-only'
      : valid ? 'Target valid · confirm this is the intended difficulty.'
      : 'Enter a target between 2.00 and 30.00 seconds (two decimal places).',
    valid ? 'ready' : 'incomplete');
  }

  const update = {
    mystery: updateMystery,
    word: updateWord,
    tick_tock: updateTimer,
  }[game];
  if (!update) return;
  editor.addEventListener('input', update);
  editor.addEventListener('change', update);
  update();
})();

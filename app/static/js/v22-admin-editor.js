/* CREW Studio trivia editor: progressive, read-only field checks.
   All ten native form sections remain visible and submit with the existing backend. */
(() => {
  'use strict';

  const workspace = document.querySelector('.studio-trivia-workspace');
  if (!workspace) return;

  const cards = [...workspace.querySelectorAll('[data-studio-question]')];
  const links = [...workspace.querySelectorAll('[data-studio-jump]')];
  const counter = workspace.querySelector('[data-studio-ready-count]');
  const normalize = (text) => String(text || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase();

  function updateStatus() {
    const prompts = cards.map((card) => {
      const number = card.dataset.studioQuestion;
      return normalize(card.querySelector(`[name="q${number}_prompt"]`)?.value);
    });
    const promptCounts = new Map();
    prompts.forEach((prompt) => {
      if (prompt) promptCounts.set(prompt, (promptCounts.get(prompt) || 0) + 1);
    });

    let ready = 0;
    let warnings = 0;
    cards.forEach((card, index) => {
      const number = card.dataset.studioQuestion;
      const prompt = prompts[index];
      const options = 'abcd'.split('').map(
        (letter) => normalize(card.querySelector(`[name="q${number}_${letter}"]`)?.value)
      );
      const answer = card.querySelector(`[name="q${number}_answer"]`);
      const filled = Boolean(prompt) && options.every(Boolean) && answer && /^(0|1|2|3)$/.test(answer.value);
      const duplicateOptions = options.some((option, position) => option && options.indexOf(option) !== position);
      const duplicatePrompt = Boolean(prompt) && promptCounts.get(prompt) > 1;
      const caution = duplicateOptions || duplicatePrompt;
      const status = caution ? 'warning' : filled ? 'ready' : 'incomplete';
      const link = links.find((element) => element.dataset.studioJump === number);
      const note = card.querySelector('[data-studio-question-note]');
      if (link) {
        link.dataset.state = status;
        link.setAttribute('aria-label', `Question ${number}, ${status === 'ready' ? 'fields complete' : caution ? 'possible duplicate' : 'incomplete'}`);
      }
      if (note) {
        note.dataset.state = status;
        note.textContent = duplicateOptions
          ? 'Possible duplicate answer choices. Check before publishing.'
          : duplicatePrompt
            ? 'This question appears more than once in the round.'
            : filled
              ? 'Fields complete. Verify the correct answer and wording before publishing.'
              : 'Incomplete question. Add a prompt and four answer choices.';
      }
      if (status === 'ready') ready += 1;
      if (status === 'warning') warnings += 1;
    });
    if (counter) {
      const next = `${ready} of ${cards.length} fields ready${warnings ? ` · ${warnings} to check` : ''}`;
      if (counter.textContent !== next) counter.textContent = next;
    }
  }

  function setActive(number) {
    links.forEach((link) => {
      const active = link.dataset.studioJump === String(number);
      link.classList.toggle('is-active', active);
      if (active) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }

  links.forEach((link) => {
    link.addEventListener('click', () => {
      const card = cards.find((item) => item.dataset.studioQuestion === link.dataset.studioJump);
      setActive(link.dataset.studioJump);
      // Native anchors handle scrolling; transfer focus for keyboard users.
      if (card) requestAnimationFrame(() => card.focus({ preventScroll: true }));
    });
  });
  cards.forEach((card) => card.addEventListener('focusin', () => setActive(card.dataset.studioQuestion)));
  workspace.addEventListener('input', updateStatus);
  workspace.addEventListener('change', updateStatus);
  updateStatus();
})();

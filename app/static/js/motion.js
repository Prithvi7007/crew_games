(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  if (reduceMotion.matches) return;

  const root = document.getElementById('crew-trivia-root');
  if (!root) return;

  let lastQuestion = '';

  function replay(node) {
    if (!node) return;
    node.classList.remove('crew-motion-enter');
    void node.offsetWidth;
    node.classList.add('crew-motion-enter');
  }

  function syncTriviaMotion() {
    const question = root.querySelector('.react-trivia-question-wrap');
    if (!question) return;

    const signature = question.textContent.trim();
    if (!signature || signature === lastQuestion) return;

    lastQuestion = signature;
    replay(question);
    replay(root.querySelector('.react-trivia-options'));
  }

  const observer = new MutationObserver(syncTriviaMotion);
  observer.observe(root, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  syncTriviaMotion();
})();

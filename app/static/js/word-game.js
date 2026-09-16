(() => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const state = window.CREW_WORD_STATE;
    const guessUrl = window.CREW_WORD_GUESS_URL;
    const board = document.getElementById('wordBoard');
    const keyboard = document.getElementById('wordKeyboard');
    const message = document.getElementById('wordMessage');
    const attemptLabel = document.getElementById('attemptLabel');
    const scoreLabel = document.getElementById('scoreLabel');
    const resultCard = document.getElementById('resultCard');
    const resultIcon = document.getElementById('resultIcon');
    const resultTitle = document.getElementById('resultTitle');
    const solutionLabel = document.getElementById('solutionLabel');
    const resultPoints = document.getElementById('resultPoints');
    const helpButton = document.getElementById('helpButton');
    const helpPanel = document.getElementById('helpPanel');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let currentRow = state.guess_count;
    let currentGuess = '';
    let locked = Boolean(state.completed || !state.playable);
    const keyboardState = {};
    const stateRank = { absent: 1, present: 2, correct: 3 };

    function getRow(index) {
        return board.querySelector(`[data-row="${index}"]`);
    }

    function updateAttemptLabel() {
        attemptLabel.textContent = `${Math.min(currentRow, 6)} / 6 guesses`;
    }

    function setMessage(text, kind = '') {
        message.textContent = text;
        message.className = `word-message ${kind}`.trim();
    }

    function setKeyboardLetter(letter, nextState) {
        if (!letter || !nextState) return;
        const prior = keyboardState[letter];
        if (!prior || stateRank[nextState] > stateRank[prior]) {
            keyboardState[letter] = nextState;
            const key = keyboard.querySelector(`[data-key="${letter}"]`);
            if (key) {
                key.classList.remove('correct', 'present', 'absent');
                key.classList.add(nextState);
                const label = nextState === 'correct'
                    ? 'correct position'
                    : nextState === 'present'
                        ? 'in the word, different position'
                        : 'not in the word';
                key.setAttribute('aria-label', `${letter}, ${label}`);
            }
        }
    }

    function fillEvaluatedRow(rowIndex, tiles, animate = false) {
        const row = getRow(rowIndex);
        if (!row) return;
        const cells = row.querySelectorAll('.word-tile');
        tiles.forEach((tile, index) => {
            const cell = cells[index];
            cell.textContent = tile.letter;
            const applyState = () => {
                cell.classList.add('locked', tile.state);
                setKeyboardLetter(tile.letter, tile.state);
            };
            if (animate && !reducedMotion) {
                cell.style.animationDelay = `${index * 115}ms`;
                cell.classList.add('flip');
                window.setTimeout(applyState, index * 115 + 250);
            } else {
                applyState();
            }
        });
    }

    function paintCurrentGuess() {
        if (currentRow >= 6) return;
        const row = getRow(currentRow);
        const cells = row.querySelectorAll('.word-tile');
        cells.forEach((cell, index) => {
            const letter = currentGuess[index] || '';
            cell.textContent = letter;
            cell.classList.toggle('filled', Boolean(letter));
        });
    }

    function shakeCurrentRow() {
        const row = getRow(currentRow);
        if (!row || reducedMotion) return;
        row.classList.remove('shake');
        void row.offsetWidth;
        row.classList.add('shake');
    }

    function lockKeyboard() {
        keyboard.querySelectorAll('button').forEach((key) => {
            key.disabled = true;
        });
    }

    function showResult(result) {
        locked = true;
        lockKeyboard();
        scoreLabel.textContent = result.score;

        const mount = document.querySelector('.word-layout');
        if (!mount || !window.CREWGameResult) return;

        const guesses = Number(result.guess_count || 0);
        window.CREWGameResult.render(mount, {
            game: 'word',
            icon: result.won ? '✓' : '◇',
            kicker: result.won ? 'WORD SOLVED' : 'ROUND COMPLETE',
            score: result.score,
            meta: result.won
                ? [`${guesses} ${guesses === 1 ? 'GUESS' : 'GUESSES'}`, String(result.solution || '').toUpperCase()]
                : [`WORD · ${String(result.solution || '').toUpperCase()}`, '6 GUESSES'],
            copy: 'Wednesday is in the books.'
        });
    }

    async function submitGuess() {
        if (locked) return;
        if (currentGuess.length !== 5) {
            setMessage('Enter all five letters first.', 'error');
            shakeCurrentRow();
            return;
        }

        locked = true;
        setMessage('Checking…');
        try {
            const response = await fetch(guessUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ guess: currentGuess })
            });
            const data = await response.json();

            if (!response.ok) {
                setMessage(data.message || 'That guess could not be submitted.', 'error');
                shakeCurrentRow();
                locked = false;
                return;
            }

            fillEvaluatedRow(currentRow, data.tiles, true);
            currentRow += 1;
            currentGuess = '';
            updateAttemptLabel();

            if (!data.completed) {
                scoreLabel.textContent = data.potential_score;
            }

            if (data.completed) {
                window.setTimeout(() => showResult(data), reducedMotion ? 0 : 700);
            } else {
                setMessage(data.won ? 'Correct!' : `${data.remaining} guesses remaining.`);
                locked = false;
            }
        } catch (_error) {
            setMessage('CREW could not reach the game server. Try again.', 'error');
            locked = false;
        }
    }

    function handleKey(key) {
        if (locked) return;
        if (key === 'ENTER') {
            submitGuess();
            return;
        }
        if (key === 'BACKSPACE') {
            currentGuess = currentGuess.slice(0, -1);
            paintCurrentGuess();
            return;
        }
        if (/^[A-Z]$/.test(key) && currentGuess.length < 5) {
            currentGuess += key;
            paintCurrentGuess();
            setMessage('');
        }
    }

    state.guesses.forEach((entry, index) => fillEvaluatedRow(index, entry.tiles, false));
    updateAttemptLabel();

    if (!state.playable && !state.completed) {
        lockKeyboard();
        setMessage('This challenge has not opened yet.', 'neutral');
    } else if (state.completed) {
        showResult(state);
    }

    keyboard.addEventListener('click', (event) => {
        const button = event.target.closest('[data-key]');
        if (!button) return;
        handleKey(button.dataset.key);
    });

    document.addEventListener('keydown', (event) => {
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        if (event.key === 'Enter') {
            event.preventDefault();
            handleKey('ENTER');
        } else if (event.key === 'Backspace') {
            event.preventDefault();
            handleKey('BACKSPACE');
        } else if (/^[a-zA-Z]$/.test(event.key)) {
            handleKey(event.key.toUpperCase());
        }
    });

    helpButton.addEventListener('click', () => {
        const willOpen = helpPanel.hidden;
        helpPanel.hidden = !willOpen;
        helpButton.setAttribute('aria-expanded', String(willOpen));
    });
})();

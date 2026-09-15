import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './trivia.css';

const LETTERS = ['A', 'B', 'C', 'D'];

function readInitialState() {
  const node = document.getElementById('trivia-state');
  if (!node) return null;
  try {
    return JSON.parse(node.textContent || '{}');
  } catch {
    return null;
  }
}

function TriviaApp({ initialState, answerUrl, returnUrl, rankingsUrl, csrfToken }) {
  const [state, setState] = useState(initialState);
  const [nextState, setNextState] = useState(null);
  const [selected, setSelected] = useState(null);
  const [resolution, setResolution] = useState(null);
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');
  const [completionStats, setCompletionStats] = useState(null);
  const stageRef = useRef(null);

  const answeredCount = nextState ? nextState.index : state.index;
  const livePoints = nextState ? nextState.correct_count * 10 : state.correct_count * 10;
  const progress = state.total ? Math.min(100, (answeredCount / state.total) * 100) : 0;
  const currentNumber = Math.min(state.index + 1, state.total);

  const resultCopy = useMemo(() => {
    const score = Number(state.score || state.correct_count * 10 || 0);
    return {
      score,
      correct: Number(state.correct_count || 0),
      total: Number(state.total || 10),
    };
  }, [state]);

  useEffect(() => {
    stageRef.current?.focus({ preventScroll: true });
  }, [state.index, state.completed]);

  async function submitAnswer(index) {
    if (status !== 'idle' || !state.question) return;
    setSelected(index);
    setStatus('submitting');
    setMessage('');

    try {
      const response = await fetch(answerUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ selected: index }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.message || 'Something went wrong. Try again.');
      }

      setResolution({
        correct: Boolean(payload.correct),
        correctIndex: Number(payload.correct_index),
        correctAnswer: payload.correct_answer,
      });
      setNextState(payload.state);
      if (payload.completed && payload.stats) setCompletionStats(payload.stats);
      setStatus('answered');
      setMessage(payload.correct ? 'Correct.' : `Not quite — ${payload.correct_answer}.`);
    } catch (error) {
      setSelected(null);
      setStatus('idle');
      setMessage(error?.message || 'Something went wrong. Try again.');
    }
  }

  function continueRound() {
    if (!nextState) return;
    setState(nextState);
    setNextState(null);
    setSelected(null);
    setResolution(null);
    setMessage('');
    setStatus('idle');
  }

  useEffect(() => {
    function onKeyDown(event) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (status === 'answered' && event.key === 'Enter') {
        event.preventDefault();
        continueRound();
        return;
      }
      if (status !== 'idle' || !state.question) return;
      const key = event.key.toLowerCase();
      const byLetter = { a: 0, b: 1, c: 2, d: 3 };
      const byNumber = { 1: 0, 2: 1, 3: 2, 4: 3 };
      const choice = key in byLetter ? byLetter[key] : byNumber[key];
      if (choice === undefined) return;
      event.preventDefault();
      submitAnswer(choice);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [status, state.index, state.question, nextState]);

  if (!state.playable && !state.completed) {
    return (
      <section className="react-trivia-stage react-trivia-upcoming" ref={stageRef} tabIndex="-1">
        <p className="react-trivia-kicker">Trivia Tuesday</p>
        <h1>This challenge hasn’t opened yet.</h1>
        <p>Come back when today’s round goes live.</p>
        <a className="react-trivia-secondary" href={returnUrl}>Back to Today</a>
      </section>
    );
  }

  if (state.completed) {
    const perfect = resultCopy.score === 100;
    const resultTitle = perfect ? 'Perfect run' : resultCopy.score >= 80 ? 'Big run' : resultCopy.score >= 60 ? 'Solid run' : 'Round complete';
    return (
      <section className={`react-trivia-stage react-trivia-result ${perfect ? 'is-perfect' : ''}`} ref={stageRef} tabIndex="-1" aria-live="polite">
        <div className="react-result-sparks" aria-hidden="true">
          <i /><i /><i /><i /><i /><i /><i /><i />
        </div>
        <div className="react-result-burst" aria-hidden="true"><span>✦</span></div>
        <p className="react-trivia-kicker">{resultTitle}</p>
        <strong className="react-result-score">{resultCopy.score}</strong>
        <span className="react-result-label">POINTS</span>
        <div className="react-result-meta">
          <span><strong>{resultCopy.correct}/{resultCopy.total}</strong> correct</span>
          {completionStats?.streak ? <span><strong>{completionStats.streak}</strong> day streak</span> : null}
        </div>
        <p className="react-result-copy">Tuesday is in the books.</p>
        <div className="react-result-actions">
          <a className="react-trivia-primary" href={rankingsUrl}>View Rankings <span>→</span></a>
          <a className="react-trivia-secondary" href={returnUrl}>Back to Today</a>
        </div>
      </section>
    );
  }

  const displayQuestion = state.question;
  const isAnswered = status === 'answered';

  return (
    <section className="react-trivia-stage" ref={stageRef} tabIndex="-1">
      <header className="react-trivia-topline">
        <div>
          <span className="react-trivia-kicker">{state.theme || 'Trivia Tuesday'}</span>
          <strong>{livePoints}<small>/100</small></strong>
        </div>
        <span>Question {currentNumber} of {state.total}</span>
      </header>

      <div className="react-trivia-progress" aria-hidden="true">
        <i style={{ width: `${progress}%` }} />
      </div>

      <div className="react-trivia-question-wrap">
        <span className="react-question-number">{String(currentNumber).padStart(2, '0')}</span>
        <h1>{displayQuestion?.prompt}</h1>
      </div>

      <div className="react-trivia-options" role="group" aria-label={`Question ${currentNumber} answer choices`}>
        {displayQuestion?.options?.map((option, index) => {
          const classes = ['react-trivia-option'];
          if (isAnswered && index === resolution?.correctIndex) classes.push('is-correct');
          if (isAnswered && index === selected && !resolution?.correct) classes.push('is-wrong');
          if (isAnswered && index !== resolution?.correctIndex && index !== selected) classes.push('is-dimmed');
          return (
            <button
              type="button"
              className={classes.join(' ')}
              key={`${state.index}-${index}`}
              onClick={() => submitAnswer(index)}
              disabled={status !== 'idle'}
              aria-pressed={selected === index}
            >
              <span className="react-option-letter">{LETTERS[index]}</span>
              <span className="react-option-copy">{option}</span>
              <span className="react-option-status" aria-hidden="true">
                {isAnswered && index === resolution?.correctIndex ? '✓' : isAnswered && index === selected ? '×' : '→'}
              </span>
            </button>
          );
        })}
      </div>

      <footer className={`react-trivia-feedback ${message ? 'is-visible' : ''} ${resolution?.correct ? 'is-success' : resolution ? 'is-error' : ''}`} aria-live="polite">
        <span>{message || (status === 'submitting' ? 'Locking it in…' : 'Choose one answer.')}</span>
        {isAnswered && (
          <button type="button" onClick={continueRound}>
            {nextState?.completed ? 'See results' : 'Next question'} <span>→</span>
          </button>
        )}
      </footer>
    </section>
  );
}

const rootNode = document.getElementById('crew-trivia-root');
const initialState = readInitialState();

if (rootNode && initialState) {
  createRoot(rootNode).render(
    <React.StrictMode>
      <TriviaApp
        initialState={initialState}
        answerUrl={rootNode.dataset.answerUrl}
        returnUrl={rootNode.dataset.returnUrl || '/home'}
        rankingsUrl={rootNode.dataset.rankingsUrl || '/leaderboard'}
        csrfToken={document.querySelector('meta[name="csrf-token"]')?.content || ''}
      />
    </React.StrictMode>,
  );
}

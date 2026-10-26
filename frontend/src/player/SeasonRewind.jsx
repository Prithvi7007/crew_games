import React, { useCallback, useEffect, useRef, useState } from 'react';
import { BadgeMedallion } from './TrophyRoom';

const GAME_ICONS = { mystery:'◆', trivia:'?', word:'W', tick_tock:'◷' };
const GAME_COLORS = { mystery:'#68f3c1', trivia:'#ffd166', word:'#7bc4ff', tick_tock:'#d7a4ff' };
const PAGES = ['opening', 'points', 'specialty', 'best-week', 'badges', 'placement', 'finale'];

export default function SeasonRewind({ data }) {
  const recap = data.rewind || {};
  const [step, setStep] = useState(0);
  const [feedback, setFeedback] = useState('');
  const touchX = useRef(null);
  const last = PAGES.length - 1;
  const next = useCallback(direction => {
    setStep(current => Math.min(last, Math.max(0, current + direction)));
    setFeedback('');
  }, [last]);

  useEffect(() => {
    function keydown(event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === 'ArrowRight' || event.key === 'PageDown') {
        event.preventDefault(); next(1);
      } else if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
        event.preventDefault(); next(-1);
      } else if (event.key === 'Home') {
        event.preventDefault(); setStep(0);
      } else if (event.key === 'End') {
        event.preventDefault(); setStep(last);
      }
    }
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, [next, last]);

  async function shareHighlights() {
    const game = recap.signature?.name || 'CREW Games';
    const text = 'My CREW Rewind S01: ' + recap.points + ' points in ' +
      recap.gamesPlayed + ' games, ' + (recap.badges?.count || 0) +
      ' badges, and my strongest game was ' + game +
      '. See you in Season Two! #CREWRewind';
    try {
      if (navigator.share) {
        await navigator.share({title:'CREW Rewind · Season 01', text});
        setFeedback('Highlights shared.');
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setFeedback('Highlights copied!');
      } else {
        setFeedback('Use your device’s share options to share this page.');
      }
    } catch (error) {
      if (error?.name !== 'AbortError') setFeedback('Sharing is unavailable on this device.');
    }
  }

  const specialty = recap.signature;
  const week = recap.bestWeek;
  const trophy = recap.badges?.featured;
  const weeklyMax = Math.max(1, ...(recap.weeklyScores || []).map(item => item.points));
  const maxGame = Math.max(1, ...(recap.gameBreakdown || []).map(item => item.points));
  const placement = recap.champion ? 'SEASON CHAMPION' :
    (recap.rank ? '#' + recap.rank + ' IN THE CREW' : 'PART OF THE CREW');

  const pages = {
    opening: <div className="rewind-copy rewind-opening">
      <span className="rewind-eyebrow">CREW · SEASON 01</span>
      <div className="rewind-avatar" aria-hidden="true">{data.shell?.user?.avatar || '✦'}</div>
      <h1>This was<br/><em>your</em> season.</h1>
      <p>{recap.username}, six weeks of CREW. Ready to see your story?</p>
      <span className="rewind-footnote">SEPT 21 — OCT 30, 2026</span>
    </div>,
    points: <div className="rewind-copy rewind-points">
      <span className="rewind-eyebrow">01 / THE NUMBERS</span>
      <h2>YOU SHOWED<br/>UP.</h2>
      <strong className="rewind-big-number">{(recap.points || 0).toLocaleString()}</strong>
      <p className="rewind-stat-label">POINTS EARNED</p>
      <div className="rewind-big-divider" aria-hidden="true"/>
      <p>Across <strong>{recap.gamesPlayed}</strong> of {recap.gamesTotal} season challenges.</p>
    </div>,
    specialty: <div className="rewind-copy rewind-specialty">
      <span className="rewind-eyebrow">02 / YOUR SIGNATURE MOVE</span>
      {specialty ? <>
        <div className="rewind-game-glyph" aria-hidden="true">{GAME_ICONS[specialty.key]}</div>
        <h2>You had a<br/><em>specialty.</em></h2>
        <strong className="rewind-specialty-name">{specialty.name}</strong>
        <p>{specialty.average} points on average, across {specialty.played} {specialty.played === 1 ? 'game' : 'games'}.</p>
        <div className="rewind-game-bars" aria-label="Total season points earned per game">
          {(recap.gameBreakdown || []).map(game => <div className="rewind-game-row" key={game.key}>
            <span>{game.name.replace(/ (Monday|Tuesday|Wednesday|Thursday)$/, '')}</span>
            <div className="rewind-game-track"><i style={{width: Math.round(100 * game.points / maxGame) + '%', background: GAME_COLORS[game.key]}}/></div>
            <strong>{game.points}</strong>
          </div>)}
        </div>
      </> : <>
        <div className="rewind-game-glyph" aria-hidden="true">✧</div>
        <h2>Your next move<br/><em>is unwritten.</em></h2>
        <p>Season Two is another chance to find your game.</p>
      </>}
    </div>,
    'best-week': <div className="rewind-copy rewind-best-week">
      <span className="rewind-eyebrow">03 / THE HIGH POINT</span>
      {week ? <>
        <h2>YOUR PEAK<br/>WEEK.</h2>
        <strong className="rewind-peak-label">WEEK {String(week.number).padStart(2, '0')}</strong>
        <strong className="rewind-peak-points">{week.points} <small>PTS</small></strong>
        <div className="rewind-weekly-chart" aria-label="Your points by season week">
          {(recap.weeklyScores || []).map(item => <div key={item.number} className={'rewind-week-column' + (item.number === week.number ? ' is-peak' : '')}>
            <div className="rewind-week-bar"><i style={{height: Math.max(item.points ? 5 : 0, Math.round(100 * item.points / weeklyMax)) + '%'}}/></div>
            <span>{String(item.number).padStart(2, '0')}</span>
          </div>)}
        </div>
        <p>{recap.weeksActive} {recap.weeksActive === 1 ? 'week' : 'weeks'} with games on the board.</p>
      </> : <>
        <h2>THE BEST<br/>IS AHEAD.</h2>
        <p>Every big streak begins with one game.</p>
      </>}
    </div>,
    badges: <div className="rewind-copy rewind-badges">
      <span className="rewind-eyebrow">04 / THE TROPHY CASE</span>
      <h2>YOU LEFT<br/>YOUR MARK.</h2>
      <strong className="rewind-badge-total">{recap.badges?.count || 0}</strong>
      <p className="rewind-stat-label">{recap.badges?.count === 1 ? 'BADGE EARNED' : 'BADGES EARNED'}</p>
      {trophy ? <div className="rewind-featured-badge">
        <BadgeMedallion badge={trophy} size="normal" seasonNumber={1}/>
        <div><span>YOUR RAREST TROPHY</span><strong>{trophy.name}</strong><small>{trophy.rarity} · S01</small></div>
      </div> : <p>There are plenty more achievements waiting for you next season.</p>}
    </div>,
    placement: <div className="rewind-copy rewind-placement">
      <span className="rewind-eyebrow">05 / YOUR PLACE IN THE STORY</span>
      <h2>YOU WERE<br/>PART OF IT.</h2>
      <strong className="rewind-placement-rank">{recap.rank ? '#' + recap.rank : '✦'}</strong>
      <p>{recap.rank ? 'YOUR SEASON RANK · ' + recap.participants + ' ACTIVE PLAYERS' : recap.participants + ' ACTIVE PLAYERS THIS SEASON'}</p>
      {recap.champion ? <span className="rewind-winner-stamp">✦ SEASON ONE CHAMPION ✦</span> :
        <span className="rewind-cohort-stamp">ONE CREW. SIX WEEKS. A LOT OF BRAGGING RIGHTS.</span>}
    </div>,
    finale: <div className="rewind-copy rewind-finale">
      <span className="rewind-eyebrow">CREW REWIND · YOUR FINALE CARD</span>
      <span className="rewind-card-avatar" aria-hidden="true">{data.shell?.user?.avatar || '✦'}</span>
      <h2>{recap.username}</h2>
      <strong className="rewind-persona">{recap.persona}</strong>
      <div className="rewind-final-stats">
        <div><strong>{recap.points}</strong><span>POINTS</span></div>
        <div><strong>{recap.gamesPlayed}</strong><span>GAMES</span></div>
        <div><strong>{recap.badges?.count || 0}</strong><span>BADGES</span></div>
      </div>
      <strong className="rewind-finale-title">{placement}</strong>
      <p>Season 01 complete. This is just the beginning.</p>
      <button type="button" className="rewind-share-button" onClick={shareHighlights}>Share my Rewind <span aria-hidden="true">↗</span></button>
      {feedback && <small className="rewind-share-feedback" role="status">{feedback}</small>}
    </div>,
  };

  return <div className="crew-rewind" onTouchStart={event => {
    touchX.current = event.touches[0]?.clientX ?? null;
  }} onTouchEnd={event => {
    if (touchX.current === null) return;
    const delta = (event.changedTouches[0]?.clientX ?? touchX.current) - touchX.current;
    touchX.current = null;
    if (Math.abs(delta) > 65) next(delta < 0 ? 1 : -1);
  }}>
    <div className="rewind-ambient" aria-hidden="true"/>
    <div className="rewind-shell">
      <header className="rewind-header">
        <a href="/home" className="rewind-brand" aria-label="Return to CREW Home">CREW<span>+</span></a>
        {recap.preview ? <span className="rewind-preview-tag">ADMIN PREVIEW · RESULTS NOT FINAL</span> : <span className="rewind-edition">REWIND / S01</span>}
        <a href="/home" className="rewind-exit" aria-label="Exit Season Rewind">✕</a>
      </header>
      <div className="rewind-progress" aria-label={'Story ' + (step + 1) + ' of ' + PAGES.length}>
        {PAGES.map((item, index) => <button type="button" key={item} aria-label={'Go to story ' + (index + 1)} aria-current={index === step ? 'step' : undefined} className={index <= step ? 'is-seen' : ''} onClick={() => { setStep(index); setFeedback(''); }}/>)}
      </div>
      <main className={'rewind-stage rewind-tone-' + PAGES[step]} aria-label="Your CREW Season One recap">
        <div className="rewind-orbit" aria-hidden="true">✳</div>
        <div key={PAGES[step]} className="rewind-scene">{pages[PAGES[step]]}</div>
        <div className="rewind-stage-footer" aria-hidden="true"><span>CREW GAMES</span><span>SEASON 01 · 2026</span></div>
      </main>
      <nav className="rewind-navigation" aria-label="Recap story controls">
        <button type="button" className="rewind-back" disabled={step === 0} onClick={() => next(-1)}>← Previous</button>
        <span className="rewind-page-count">{String(step + 1).padStart(2, '0')} / {String(PAGES.length).padStart(2, '0')}</span>
        <button type="button" className="rewind-next" onClick={() => step === last ? setStep(0) : next(1)}>{step === last ? 'Replay ↺' : 'Next →'}</button>
      </nav>
    </div>
  </div>;
}

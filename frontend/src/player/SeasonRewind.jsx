import React, { useCallback, useEffect, useRef, useState } from 'react';
import { BadgeMedallion } from './TrophyRoom';
import { AnimatePresence, LazyMotion, MotionConfig, domAnimation, m, useReducedMotion } from 'motion/react';

const GAME_ICONS = { mystery:'◆', trivia:'?', word:'W', tick_tock:'◷' };
const GAME_COLORS = { mystery:'var(--crew-game-mystery, #55e6ac)', trivia:'var(--crew-game-trivia, #ffbd45)', word:'var(--crew-game-word, #55b9ff)', tick_tock:'var(--crew-game-tick-tock, #c55cff)' };
const PAGES = ['opening', 'points', 'specialty', 'best-week', 'badges', 'placement', 'finale'];

// Direction-dependent scenes; only transform and opacity are animated.
const SCENE_VARIANTS = {
  enter: direction => ({ opacity: 0, x: direction * 22, scale: .986 }),
  center: { opacity: 1, x: 0, scale: 1 },
  exit: direction => ({ opacity: 0, x: direction * -18, scale: .994 }),
};

export default function SeasonRewind({ data }) {
  const recap = data.rewind || {};
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [feedback, setFeedback] = useState('');
  const touchX = useRef(null);
  const reduceMotion = useReducedMotion();
  const revealStart = reduceMotion ? false : { opacity: 0, y: 12, scale: .95 };
  const revealTransition = reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 190, damping: 24, delay: .12 };
  const last = PAGES.length - 1;
  const next = useCallback(direction => {
    setDirection(direction < 0 ? -1 : 1);
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
        event.preventDefault(); setDirection(-1); setStep(0);
      } else if (event.key === 'End') {
        event.preventDefault(); setDirection(1); setStep(last);
      }
    }
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, [next, last]);

  async function shareHighlights() {
    const game = recap.signature?.name || 'CREW Games';
    const playStyle = recap.insights?.playStyle;
    const text = 'My CREW Rewind S01: ' +
      (playStyle ? playStyle.title + '. ' + playStyle.evidence + ' ' : '') +
      recap.points + ' points in ' +
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
  const insights = recap.insights || {};
  const weeklyMax = Math.max(1, ...(recap.weeklyScores || []).map(item => item.points));
  const maxGame = Math.max(1, ...(recap.gameBreakdown || []).map(item => item.points));
  const placement = recap.champion ? 'SEASON CHAMPION' :
    (recap.rank ? '#' + recap.rank + ' IN THE CREW' : 'PART OF THE CREW');

  const pages = {
    opening: <div className="rewind-copy rewind-opening">
      <span className="rewind-eyebrow">CREW REWIND <span className="rewind-eyebrow-rule"/> ORIGINAL SERIES · S01</span>
      <div className="rewind-opening-art" aria-hidden="true">
        <span className="rewind-opening-season">SEASON<span>01</span></span>
        <span className="rewind-opening-cross">✳</span>
        <m.span className="rewind-avatar" initial={reduceMotion ? false : {opacity: 0, scale: .78, rotate: -14}} animate={{opacity: 1, scale: 1, rotate: -8}} transition={revealTransition}>{data.shell?.user?.avatar || '✦'}</m.span>
      </div>
      <div className="rewind-opening-story">
        <span className="rewind-chapter-kicker">YOUR PLAYER TYPE / {insights.playStyle?.title || 'THE NEXT CHAPTER'}</span>
        <h1>THIS WAS<br/><em>YOUR</em><br/>SEASON.</h1>
        <p>{insights.playStyle?.evidence || 'Six weeks. Your games. Your moments. One unforgettable first season.'}</p>
      </div>
      <div className="rewind-opening-endcard">
        <span>SEPT 21 — OCT 30, 2026</span>
        <span>7 CHAPTERS / 1 STORY <span aria-hidden="true">↗</span></span>
      </div>
    </div>,
    points: <div className="rewind-copy rewind-points">
      <span className="rewind-eyebrow">01 / THE NUMBERS</span>
      <div className="rewind-points-composition">
        <div className="rewind-points-story">
          <span className="rewind-chapter-kicker">EVERY GAME ADDED UP.</span>
          <h2>YOU<br/>SHOWED<br/><em>UP.</em></h2>
        </div>
        <div className="rewind-points-total">
          <span className="rewind-scenery" aria-hidden="true">PTS</span>
          <m.strong className="rewind-big-number" initial={revealStart} animate={{opacity: 1, y: 0, scale: 1}} transition={revealTransition}>{(recap.points || 0).toLocaleString()}</m.strong>
          <p className="rewind-stat-label">YOUR TOTAL POINTS</p>
        </div>
      </div>
      <div className="rewind-points-footer">
        <span className="rewind-points-progress"><strong>{recap.gamesPlayed || 0}</strong><span>GAMES<br/>PLAYED</span></span>
        <span className="rewind-points-divider" aria-hidden="true"/>
        <span className="rewind-points-footnote">{insights.averageScore == null ? 'YOUR SEASON IS STILL UNWRITTEN' : <>AVERAGED <strong>{insights.averageScore} POINTS PER GAME</strong><br/>LONGEST RUN: <strong>{insights.longestWeeklyStreak} {insights.longestWeeklyStreak === 1 ? 'WEEK' : 'WEEKS'}</strong></>}</span>
      </div>
    </div>,
    specialty: <div className="rewind-copy rewind-specialty">
      <span className="rewind-eyebrow">02 / YOUR SIGNATURE MOVE</span>
      {specialty ? <>
        <div className="rewind-specialty-feature">
          <m.div className="rewind-game-glyph" aria-hidden="true" initial={revealStart} animate={{opacity: 1, y: 0, scale: 1}} transition={revealTransition}>{GAME_ICONS[specialty.key] || '✦'}</m.div>
          <div className="rewind-specialty-headline">
            <span className="rewind-chapter-kicker">EVERYONE HAS THEIR GAME.</span>
            <h2>THIS WAS<br/><em>YOURS.</em></h2>
            <strong className="rewind-specialty-name">{specialty.name}</strong>
            <p>{specialty.average} points on average across {specialty.played} {specialty.played === 1 ? 'game' : 'games'}.</p>
            {insights.peerComparison ? <div className="rewind-peer-benchmark" aria-label="Game comparison with other CREW players">
              <span>YOUR AVERAGE <strong>{insights.peerComparison.yourAverage}</strong></span>
              <span>OTHERS' AVERAGE <strong>{insights.peerComparison.crewAverage}</strong></span>
              <small>VS {insights.peerComparison.playersCompared} OTHER PLAYERS IN THIS GAME</small>
            </div> : <span className="rewind-specialty-note">YOUR PERSONAL GAME AVERAGE / {specialty.average} PTS</span>}
          </div>
        </div>
        <div className="rewind-game-bars" aria-label="Total season points earned per game">
          <span className="rewind-data-caption">THE SCOREBOARD / YOUR GAME MIX</span>
          {(recap.gameBreakdown || []).map(game => <div className="rewind-game-row" key={game.key}>
            <span>{game.name.replace(/ (Monday|Tuesday|Wednesday|Thursday)$/, '')}</span>
            <div className="rewind-game-track"><i style={{width: Math.round(100 * game.points / maxGame) + '%', background: GAME_COLORS[game.key]}}/></div>
            <strong>{game.points}</strong>
          </div>)}
        </div>
      </> : <>
        <div className="rewind-specialty-feature rewind-specialty-unwritten">
          <div className="rewind-game-glyph" aria-hidden="true">✧</div>
          <div className="rewind-specialty-headline"><h2>THE BEST<br/><em>IS AHEAD.</em></h2><p>Season Two is another chance to find your game.</p></div>
        </div>
      </>}
    </div>,
    'best-week': <div className="rewind-copy rewind-best-week">
      <span className="rewind-eyebrow">03 / YOUR HIGH POINT</span>
      {week ? <>
        <div className="rewind-week-feature">
          <div className="rewind-week-wordmark" aria-hidden="true">PEAK</div>
          <span className="rewind-chapter-kicker">SOME WEEKS JUST HIT DIFFERENT.</span>
          <h2>YOUR<br/><em>PEAK.</em></h2>
          <strong className="rewind-peak-label">WEEK {String(week.number).padStart(2, '0')}</strong>
          <m.strong className="rewind-peak-points" initial={revealStart} animate={{opacity: 1, y: 0, scale: 1}} transition={revealTransition}>{week.points} <small>PTS</small></m.strong>
          {insights.highestGame && <span className="rewind-personal-best">BEST SINGLE GAME: <strong>{insights.highestGame.score} PTS / {insights.highestGame.game}</strong></span>}
        </div>
        <div className="rewind-weekly-panel">
          <span className="rewind-data-caption">YOUR SEASON / WEEK BY WEEK</span>
          <div className="rewind-weekly-chart" aria-label="Your points by season week">
            {(recap.weeklyScores || []).map(item => <div key={item.number} className={'rewind-week-column' + (item.number === week.number ? ' is-peak' : '')}>
              <div className="rewind-week-bar"><i style={{height: Math.max(item.points ? 5 : 0, Math.round(100 * item.points / weeklyMax)) + '%'}}/></div>
              <span>{String(item.number).padStart(2, '0')}</span>
            </div>)}
          </div>
          <p>{recap.weeksActive} {recap.weeksActive === 1 ? 'week' : 'weeks'} with games on the board.</p>
          {insights.momentum && <div className="rewind-momentum" aria-label="First versus second half game performance">
            <span>FIRST HALF AVG <strong>{insights.momentum.firstAverage}</strong></span>
            <span>SECOND HALF AVG <strong>{insights.momentum.secondAverage}</strong></span>
            <em>{insights.momentum.direction === 'up' ? 'FINISHED STRONGER' : insights.momentum.direction === 'steady' ? 'CONSISTENT FORM' : 'ROOM FOR A COMEBACK'}</em>
          </div>}
        </div>
      </> : <>
        <div className="rewind-week-feature"><span className="rewind-chapter-kicker">THE STORY CONTINUES.</span><h2>THE BEST<br/><em>IS AHEAD.</em></h2><p>Every big streak begins with one game.</p></div>
      </>}
    </div>,
    badges: <div className="rewind-copy rewind-badges">
      <span className="rewind-eyebrow">04 / THE TROPHY CASE</span>
      <div className="rewind-badge-header">
        <h2>YOU LEFT<br/><em>YOUR MARK.</em></h2>
        <div className="rewind-badge-counter">
          <m.strong className="rewind-badge-total" initial={revealStart} animate={{opacity: 1, y: 0, scale: 1}} transition={revealTransition}>{recap.badges?.count || 0}</m.strong>
          <span>{recap.badges?.count === 1 ? 'BADGE' : 'BADGES'}<br/>EARNED</span>
        </div>
      </div>
      {trophy ? <m.div className="rewind-featured-badge" initial={reduceMotion ? false : {opacity: 0, y: 14}} animate={{opacity: 1, y: 0}} transition={reduceMotion ? {duration: 0} : {duration: .45, delay: .18}}>
        <div className="rewind-trophy-spotlight">
          <span className="rewind-trophy-shine" aria-hidden="true"/>
          <BadgeMedallion badge={trophy} size="normal" seasonNumber={1}/>
        </div>
        <div className="rewind-trophy-label"><span>THE RAREST IN YOUR COLLECTION</span><strong>{trophy.name}</strong><small>{trophy.rarity} / SEASON 01</small></div>
      </m.div> : <div className="rewind-badge-empty"><span aria-hidden="true">✦</span><p>Every legendary collection starts somewhere. Your next season awaits.</p></div>}
      <span className="rewind-badge-serial">EARNED. NOT GIVEN. <span aria-hidden="true">✳</span> CREW / S01</span>
    </div>,
    placement: <div className="rewind-copy rewind-placement">
      <span className="rewind-eyebrow">05 / YOUR PLACE IN THE STORY</span>
      <div className="rewind-placement-center">
        <span className="rewind-placement-backdrop" aria-hidden="true">RANK</span>
        <span className="rewind-chapter-kicker">THERE WAS ONLY ONE YOU.</span>
        <h2>YOU WERE<br/><em>IN THE MIX.</em></h2>
        <m.strong className="rewind-placement-rank" initial={revealStart} animate={{opacity: 1, y: 0, scale: 1}} transition={revealTransition}>{recap.rank ? '#' + recap.rank : '✦'}</m.strong>
        <p>{recap.rank ? 'YOUR SEASON RANK · ' + recap.participants + ' ACTIVE PLAYERS' : recap.participants + ' ACTIVE PLAYERS THIS SEASON'}</p>
        {insights.outpacedPercent > 0 && <span className="rewind-placement-insight">OUTSCORED <strong>{insights.outpacedPercent}%</strong> OF OTHER ACTIVE PLAYERS</span>}
      </div>
      {recap.champion ? <span className="rewind-winner-stamp">✦ SEASON ONE CHAMPION ✦</span> :
        <span className="rewind-cohort-stamp">ONE CREW. SIX WEEKS. A LOT OF BRAGGING RIGHTS.</span>}
    </div>,
    finale: <div className="rewind-copy rewind-finale">
      <span className="rewind-eyebrow">06 / YOUR SEASON, FOREVER</span>
      <div className="rewind-finale-poster">
        <div className="rewind-poster-masthead"><span>CREW REWIND</span><span>S01 / 2026</span></div>
        <div className="rewind-poster-identity">
          <m.span className="rewind-card-avatar" aria-hidden="true" initial={reduceMotion ? false : {opacity: 0, scale: .84}} animate={{opacity: 1, scale: 1}} transition={revealTransition}>{data.shell?.user?.avatar || '✦'}</m.span>
          <span className="rewind-poster-edition">OFFICIAL SEASON RECORD · Nº 01</span>
          <h2>{recap.username}</h2>
          <strong className="rewind-persona">{insights.playStyle?.title || recap.persona}</strong>
          <span className="rewind-poster-evidence">{insights.playStyle?.evidence || 'Your story is only beginning.'}</span>
        </div>
        <m.div className="rewind-final-stats" initial={reduceMotion ? false : {opacity: 0, y: 12}} animate={{opacity: 1, y: 0}} transition={reduceMotion ? {duration: 0} : {duration: .4, delay: .18}}>
          <div><strong>{insights.averageScore ?? '—'}</strong><span>AVG / GAME</span></div>
          <div><strong>{insights.gamesTried ?? 0}/4</strong><span>GAME TYPES</span></div>
          <div><strong>{insights.longestWeeklyStreak ?? 0}</strong><span>WEEK RUN</span></div>
        </m.div>
        <div className="rewind-poster-footer">
          <strong className="rewind-finale-title">{placement}</strong>
          <span>ONE OF THE ORIGINAL CREW.</span>
        </div>
      </div>
      <div className="rewind-finale-actions">
        <p>Season 01 complete. This is just the beginning.</p>
        <button type="button" className="rewind-share-button" onClick={shareHighlights}>Share my Rewind <span aria-hidden="true">↗</span></button>
        {feedback && <small className="rewind-share-feedback" role="status">{feedback}</small>}
      </div>
    </div>,
  };

  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user"><div className="crew-rewind" onTouchStart={event => {
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
        {PAGES.map((item, index) => <button type="button" key={item} aria-label={'Go to story ' + (index + 1)} aria-current={index === step ? 'step' : undefined} className={index <= step ? 'is-seen' : ''} onClick={() => { setDirection(index < step ? -1 : 1); setStep(index); setFeedback(''); }}/>)}
      </div>
      <main className={'rewind-stage rewind-tone-' + PAGES[step] + (PAGES[step] === 'specialty' && GAME_COLORS[specialty?.key] ? ' rewind-game-' + specialty.key : '')} aria-label="Your CREW Season One recap">
        <AnimatePresence mode="wait" initial={false} custom={direction}>
          <m.div key={PAGES[step]} className="rewind-scene" custom={direction} variants={SCENE_VARIANTS}
            initial={reduceMotion ? false : 'enter'} animate="center" exit={reduceMotion ? undefined : 'exit'}
            transition={reduceMotion ? {duration: 0} : {duration: .38, ease: [.22, 1, .36, 1]}}>
            {pages[PAGES[step]]}
          </m.div>
        </AnimatePresence>
        <div className="rewind-stage-footer" aria-hidden="true"><span>CREW GAMES</span><span>SEASON 01 · 2026</span></div>
      </main>
      <nav className="rewind-navigation" aria-label="Recap story controls">
        <button type="button" className="rewind-back" disabled={step === 0} onClick={() => next(-1)}>← Previous</button>
        <span className="rewind-page-count" role="status" aria-live="polite" aria-atomic="true">{String(step + 1).padStart(2, '0')} / {String(PAGES.length).padStart(2, '0')}</span>
        <button type="button" className="rewind-next" onClick={() => { if (step === last) { setDirection(1); setStep(0); setFeedback(''); } else next(1); }}>{step === last ? 'Replay ↺' : 'Next →'}</button>
      </nav>
    </div>
  </div></MotionConfig></LazyMotion>;
}

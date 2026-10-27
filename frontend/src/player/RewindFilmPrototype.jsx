import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, LazyMotion, MotionConfig, domAnimation, m, useReducedMotion } from 'motion/react';

const ORDER = ['mystery', 'trivia', 'word', 'tick_tock'];
const GAMES = {
  mystery: { name: 'Mystery', symbol: '◆', color: '#5ce9b4' },
  trivia: { name: 'Trivia', symbol: '?', color: '#ffcc66' },
  word: { name: 'Wordle', symbol: 'W', color: '#72c8ff' },
  tick_tock: { name: 'Tick-Tock', symbol: '◷', color: '#cc9aff' },
};
const ease = [.22, 1, .36, 1];

export default function RewindFilmPrototype({ data }) {
  const recap = data.rewind || {};
  const reduce = useReducedMotion();
  const history = recap.weeklyGameScores || [];
  const [week, setWeek] = useState(0);
  const [phase, setPhase] = useState('race');
  const [playing, setPlaying] = useState(false);
  const totals = useMemo(() => ORDER.map(key => ({
    key, total: history.slice(0, week + 1).reduce((sum, item) => sum + (item.games?.[key] || 0), 0),
  })).sort((a, b) => b.total - a.total || ORDER.indexOf(a.key) - ORDER.indexOf(b.key)), [history, week]);
  const winner = recap.signature?.key || (totals[0]?.total ? totals[0].key : null);
  const discovery = recap.signature;
  const peak = totals[0]?.total || 0;
  const noGames = !recap.gamesPlayed;

  // Only an explicit user gesture starts playback. Each frame is one real season week.
  useEffect(() => {
    if (!playing || reduce || phase !== 'race') return undefined;
    if (week >= history.length - 1) { setPlaying(false); return undefined; }
    const id = setTimeout(() => setWeek(value => Math.min(history.length - 1, value + 1)), 950);
    return () => clearTimeout(id);
  }, [playing, reduce, phase, week, history.length]);

  function begin() {
    setWeek(0);
    setPhase('race');
    setPlaying(!reduce);
  }
  function discover() {
    setPlaying(false);
    setPhase('reveal');
  }
  function replay() {
    setPhase('race');
    setWeek(0);
    setPlaying(false);
  }

  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user">
    <div className={'rewind-film rewind-film-' + phase} style={{'--film-accent': GAMES[winner]?.color || '#a5d8ff'}}>
      <a className="rewind-film-exit" href="/rewind?preview=1" aria-label="Exit film prototype and return to original Rewind">✕ <span>EXIT PREVIEW</span></a>
      <span className="rewind-film-watermark">EXPERIMENTAL · OWNER PREVIEW</span>
      <div className="rewind-film-canvas">
        <AnimatePresence mode="wait" initial={false}>
          {phase === 'race' ? <m.section key="race" className="rewind-film-scene" initial={reduce ? false : {opacity:0, scale:.97}} animate={{opacity:1,scale:1}} exit={reduce ? undefined : {opacity:0,scale:1.1,filter:'blur(14px)'}} transition={{duration:reduce ? 0 : .65,ease}}>
            <div className="rewind-film-intro">
              <span className="rewind-film-kicker">{recap.username || 'YOUR'} · SEASON 01</span>
              <h1>Your games.<br/><em>Your story.</em></h1>
              <p>{noGames ? 'The season is yours to write.' : 'Watch your season take shape.'}</p>
            </div>
            <div className="rewind-film-track" role="img" aria-label={'Game scores through week ' + (week + 1) + ': ' + totals.map(game => GAMES[game.key].name + ' ' + game.total + ' points').join(', ')}>
              {totals.map((game, index) => <m.div className="rewind-film-runner" key={game.key}
                layout={!reduce} transition={{layout:{type:'spring',stiffness:170,damping:27}}}
                style={{'--runner-color':GAMES[game.key].color}}>
                <div className="rewind-film-lane">
                  <span className="rewind-film-symbol" aria-hidden="true">{GAMES[game.key].symbol}</span>
                  <span className="rewind-film-runner-name">{GAMES[game.key].name}</span>
                  <strong>{game.total.toLocaleString()}</strong>
                </div>
                <div className="rewind-film-line"><m.div initial={false} animate={{width:peak ? Math.max(0,100*game.total/peak)+'%' : '0%'}} transition={{duration:reduce?0:.62,ease}}/></div>
                <span className="rewind-film-place">{String(index+1).padStart(2,'0')}</span>
              </m.div>)}
            </div>
            <div className="rewind-film-bottom">
              <div className="rewind-film-time">
                <span>SEASON TIMELINE</span>
                <strong>{history.length ? 'WEEK ' + String(week+1).padStart(2,'0') : 'NO GAMES YET'}</strong>
                <div className="rewind-film-weeks" aria-label="Choose a season week">
                  {history.map((item,index) => <button key={item.number} type="button" className={index<=week?'is-active':''} aria-label={'View week '+item.number} aria-current={week===index?'step':undefined} onClick={() => {setPlaying(false);setWeek(index);}}><span/></button>)}
                </div>
              </div>
              <div className="rewind-film-actions">
                <button type="button" onClick={begin}>{playing ? 'RESTART' : 'PLAY SEASON'} <span aria-hidden="true">▶</span></button>
                <button type="button" className="is-primary" onClick={discover}>THE REVEAL <span aria-hidden="true">→</span></button>
              </div>
            </div>
          </m.section> : <m.section key="reveal" className="rewind-film-scene rewind-film-discovery" initial={reduce ? false : {opacity:0,scale:.87,filter:'blur(15px)'}} animate={{opacity:1,scale:1,filter:'blur(0px)'}} exit={reduce ? undefined : {opacity:0,scale:1.05}} transition={{duration:reduce?0:.8,ease}}>
            <div className="rewind-film-halo" aria-hidden="true"/>
            <m.div className="rewind-film-reveal-symbol" aria-hidden="true" initial={reduce?false:{scale:.45,rotate:-26}} animate={{scale:1,rotate:0}} transition={{type:'spring',stiffness:90,damping:15}}>
              {GAMES[winner]?.symbol || '✦'}
            </m.div>
            <div className="rewind-film-reveal-copy">
              <span className="rewind-film-kicker">THE GAME THAT DEFINED YOU</span>
              <h2>{discovery ? GAMES[discovery.key]?.name || discovery.name : 'Your story is beginning.'}</h2>
              {discovery ? <p>Your average was <strong>{discovery.average} points</strong> across {discovery.played} {discovery.played === 1 ? 'game' : 'games'}. This was your strongest game by average score—not simply the one you played most.</p> : <p>Your strongest game will reveal itself once you start playing.</p>}
              {recap.insights?.peerComparison && <p className="rewind-film-contrast">You averaged {Math.abs(recap.insights.peerComparison.difference)} points {recap.insights.peerComparison.difference>=0?'above':'below'} the average of {recap.insights.peerComparison.playersCompared} other players in this game.</p>}
            </div>
            <button type="button" className="rewind-film-replay" onClick={replay}>← REPLAY YOUR SEASON</button>
          </m.section>}
        </AnimatePresence>
      </div>
      <div className="rewind-film-footer"><span>CREW / REWIND LAB</span><span>{phase==='race'?'01 — YOUR SEASON':'02 — YOUR SIGNATURE'}</span></div>
    </div>
  </MotionConfig></LazyMotion>;
}

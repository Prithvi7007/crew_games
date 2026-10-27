import React, { useEffect, useMemo, useState } from 'react';
import { LazyMotion, MotionConfig, domAnimation, m, useReducedMotion } from 'motion/react';

const ORDER = ['mystery', 'trivia', 'word', 'tick_tock'];
const GAMES = {
  mystery: {name: 'Mystery', symbol: '◆', color: '#55e6ac'},
  trivia: {name: 'Trivia', symbol: '?', color: '#ffbd45'},
  word: {name: 'Wordle', symbol: 'W', color: '#55b9ff'},
  tick_tock: {name: 'Tick-Tock', symbol: '◷', color: '#c55cff'},
};
const EASE = [.2, .8, .2, 1];
const LANES = [90, 190, 290, 390];
const SUM = (weeks, limit) => ORDER.map(key => ({
  key,
  score: weeks.slice(0, limit + 1).reduce((total, row) => total + (Number(row.games?.[key]) || 0), 0),
}));

export function filmDiscovery(weeks, gameCount) {
  const totals = SUM(weeks, weeks.length - 1).sort((a,b) => b.score - a.score || ORDER.indexOf(a.key) - ORDER.indexOf(b.key));
  const topScore = totals[0]?.score || 0;
  const leaders = topScore ? totals.filter(item => item.score === topScore) : [];
  const total = totals.reduce((n,item)=>n+item.score, 0);
  let previous = null;
  let leadChanges = 0;
  for (let w=0; w<weeks.length; w+=1) {
    const atWeek = SUM(weeks,w).sort((a,b)=>b.score-a.score);
    const unique = atWeek[0]?.score > 0 && atWeek[0].score > atWeek[1]?.score ? atWeek[0].key : null;
    if (unique && previous && unique !== previous) leadChanges += 1;
    if (unique) previous = unique;
  }
  return {
    total, leaders, topScore, leadChanges,
    percent: total ? Math.round(100 * topScore / total) : 0,
    noGames: !gameCount || !total,
  };
}

export default function RewindFilmPrototype({data}) {
  const recap = data.rewind || {};
  const reduce = useReducedMotion();
  const weeks = recap.weeklyGameScores || [];
  const [week, setWeek] = useState(0);
  const [phase, setPhase] = useState('intro');
  const [playing, setPlaying] = useState(false);
  const discovery = useMemo(()=>filmDiscovery(weeks,recap.gamesPlayed),[weeks,recap.gamesPlayed]);
  const scores = useMemo(()=>SUM(weeks,week),[weeks,week]);
  const maximum = Math.max(1,...SUM(weeks,weeks.length-1).map(g=>g.score));
  const lead = discovery.leaders[0]?.key;
  const singleLeader = discovery.leaders.length === 1;
  const theme = GAMES[lead]?.color || '#55b9ff';
  const fullWeek = week >= weeks.length - 1;

  useEffect(() => {
    if (!playing || phase !== 'race' || reduce) return undefined;
    const id = setTimeout(()=>{
      if (week >= weeks.length - 1) {
        setPlaying(false);
        setPhase('discovery');
      } else setWeek(old => Math.min(old+1,weeks.length-1));
    }, 1030);
    return () => clearTimeout(id);
  },[week,weeks.length,playing,phase,reduce]);

  function play() {
    if (reduce || !weeks.length) {
      setWeek(Math.max(0,weeks.length-1));
      setPlaying(false);
      setPhase('discovery');
      return;
    }
    if (phase === 'discovery' || phase === 'intro' || fullWeek) setWeek(0);
    setPhase('race');
    setPlaying(true);
  }
  function chooseWeek(i) {
    setWeek(i);
    setPhase('race');
    setPlaying(false);
  }
  function reveal() {
    setWeek(Math.max(0,weeks.length-1));
    setPlaying(false);
    setPhase('discovery');
  }
  function replay() {
    setWeek(0);
    setPlaying(false);
    setPhase('intro');
  }

  const filmTitle = discovery.noGames
    ? 'Your next chapter is unwritten.'
    : !singleLeader
      ? 'You had more than one frontrunner.'
      : 'One game kept pulling ahead.';
  const revealName = discovery.noGames ? 'Season Two awaits'
    : discovery.leaders.map(g=>GAMES[g.key].name).join(' + ');
  const detail = discovery.noGames
    ? 'There are no completed games in this season to compare yet.'
    : singleLeader
      ? GAMES[lead].name + ' earned ' + discovery.topScore + ' of your ' + discovery.total +
        ' points (' + discovery.percent + '%)—more than any other game.'
      : 'These games tied at ' + discovery.topScore + ' points each. Your season had a shared lead.';

  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user">
    <main className={'rewind-film rewind-film-' + phase} style={{'--film-accent':theme}}
      aria-label="Experimental Season One interactive film">
      <div className="rewind-film-atmosphere" aria-hidden="true"/>
      <header className="rewind-film-header">
        <span className="rewind-film-mark">CREW<span>+</span><small>REWIND · 01</small></span>
        <span className="rewind-film-preview">OWNER PREVIEW · NOT THE LIVE REWIND</span>
        <a href="/rewind?preview=1" className="rewind-film-exit" aria-label="Return to the original Rewind">✕</a>
      </header>

      <section className="rewind-film-field">
        <div className="rewind-film-narration" aria-live="polite">
          <m.p className="rewind-film-introline" animate={{opacity:1}} initial={false}>
            {phase==='intro' ? (recap.username || 'YOUR') + ', THIS WAS YOUR SEASON.'
              : phase==='race' ? 'WATCH THE SEASON UNFOLD' : 'HERE IS WHAT EMERGED'}
          </m.p>
          <m.h1 layout animate={{opacity:1}} transition={{duration:reduce?0:.5}}>
            {phase === 'intro' ? <>Every game<br/><em>left a mark.</em></>
              : phase === 'race' ? <>Six weeks.<br/><em>Four contenders.</em></>
              : filmTitle}
          </m.h1>
        </div>

        <div className="rewind-film-arena">
          <svg viewBox="0 0 940 480" preserveAspectRatio="xMidYMid meet"
            role="img" aria-label={'Cumulative scores through week '+(week+1)+': '+
              scores.map(g=>GAMES[g.key].name+' '+g.score+' points').join(', ')}>
            <defs>
              {ORDER.map(key=><linearGradient id={'film-stream-'+key} key={key} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={GAMES[key].color} stopOpacity="0"/>
                <stop offset="62%" stopColor={GAMES[key].color} stopOpacity=".35"/>
                <stop offset="100%" stopColor={GAMES[key].color} stopOpacity=".9"/>
              </linearGradient>)}
            </defs>
            {scores.map((game,index)=>{
              const y=LANES[index];
              const x=140+Math.round((game.score/maximum)*600);
              const targetX=phase==='discovery' && discovery.leaders.some(item=>item.key===game.key) ? 490 : x;
              const targetY=phase==='discovery' && discovery.leaders.some(item=>item.key===game.key) ? 220+ (discovery.leaders.length>1 ? (discovery.leaders.findIndex(item=>item.key===game.key)*112 -56) : 0) : y;
              const isLeader=discovery.leaders.some(item=>item.key===game.key);
              const faded=phase==='discovery' && !isLeader;
              const duration=reduce?0:.85;
              return <g key={game.key} className={'rewind-film-contender rewind-film-contender-'+game.key}>
                <m.path d={'M 82 '+y+' C '+(90+x*.22)+' '+(y-44)+' '+(x-65)+' '+(y+24)+' '+x+' '+y}
                  fill="none" stroke={'url(#film-stream-'+game.key+')'} strokeWidth="5" strokeLinecap="round"
                  initial={false} animate={{opacity:phase==='discovery' ? .06 : .9,
                    d:'M 82 '+y+' C '+(90+targetX*.22)+' '+(y-44)+' '+(targetX-65)+' '+(y+24)+' '+targetX+' '+targetY}}
                  transition={{duration,ease:EASE}}/>
                <m.circle initial={false} animate={{cx:targetX,cy:targetY,r:phase==='discovery' && isLeader?64:25,opacity:faded?0:1}}
                  transition={{duration,ease:EASE}} fill="#061725" stroke={GAMES[game.key].color}
                  strokeWidth={phase==='discovery'&&isLeader?3:2}/>
                <m.text initial={false}
                  animate={{x:targetX,y:targetY+9,opacity:faded?0:1,fontSize:phase==='discovery'&&isLeader?70:28}}
                  transition={{duration,ease:EASE}}
                  textAnchor="middle" fontWeight="900" fill={GAMES[game.key].color}>
                  {GAMES[game.key].symbol}
                </m.text>
                <m.text initial={false} animate={{x:phase==='discovery'?targetX:Math.min(830,x+38),y:phase==='discovery'?targetY+94:y+6,opacity:faded?0:1}}
                  transition={{duration,ease:EASE}} textAnchor={phase==='discovery'?'middle':'start'}
                  fontSize={phase==='discovery'?20:18} fill="#e2f4ff" fontWeight="800">
                  {GAMES[game.key].name}{phase==='discovery'?'':'  ·  '+game.score+' pts'}
                </m.text>
              </g>;
            })}
          </svg>
        </div>

        <div className="rewind-film-insight" aria-live="polite">
          {phase==='intro' ? <p>Your results will move the four games across the screen—one week at a time.</p>
            : phase==='race' ? <p>Week {week+1} of {weeks.length || 6}. Every movement is drawn from your actual scores.</p>
            : <div className="rewind-film-discovery-copy">
                <span>YOUR POINTS LEADER</span>
                <h2>{revealName}</h2>
                <p>{detail}</p>
                {discovery.leadChanges>0 && <p className="rewind-film-twist">The lead changed {discovery.leadChanges} {discovery.leadChanges===1?'time':'times'} along the way.</p>}
                {singleLeader && recap.signature?.key && recap.signature.key!==lead &&
                  <p className="rewind-film-twist">The twist: {GAMES[recap.signature.key].name} had your highest average score per game.</p>}
              </div>}
        </div>
      </section>

      <footer className="rewind-film-controls">
        <div className="rewind-film-timeline" role="group" aria-label="Select a week in the season">
          {weeks.map((row,i)=><button type="button" key={row.number} onClick={()=>chooseWeek(i)}
            aria-current={phase==='race'&&week===i?'step':undefined}
            aria-label={'See week '+row.number+' results'}><span>{String(row.number).padStart(2,'0')}</span></button>)}
        </div>
        <div className="rewind-film-buttons">
          {phase==='intro' ? <button className="rewind-film-primary" type="button" onClick={play}>Play my season <span aria-hidden="true">→</span></button>
            : phase==='race' ? <>
              <button type="button" onClick={()=>setPlaying(v=>!v)} disabled={!!reduce}>{playing?'Pause':'Play'} <span aria-hidden="true">{playing?'Ⅱ':'▶'}</span></button>
              <button className="rewind-film-primary" type="button" onClick={reveal}>Discover my pattern <span aria-hidden="true">→</span></button>
            </> : <button type="button" onClick={replay}>Replay my season ↺</button>}
        </div>
      </footer>
    </main>
  </MotionConfig></LazyMotion>;
}

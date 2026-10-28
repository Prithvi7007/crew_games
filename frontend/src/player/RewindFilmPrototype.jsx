import React, { useEffect, useMemo, useState } from 'react';
import { LazyMotion, MotionConfig, domAnimation, m, useReducedMotion } from 'motion/react';
import { BadgeMedallion } from './TrophyRoom';

const ORDER = ['mystery', 'trivia', 'word', 'tick_tock'];
const GAMES = {
  mystery: {name: 'Mystery', symbol: '◆', color: '#55e6ac'},
  trivia: {name: 'Trivia', symbol: '?', color: '#ffbd45'},
  word: {name: 'Wordle', symbol: 'W', color: '#55b9ff'},
  tick_tock: {name: 'Tick-Tock', symbol: '◷', color: '#c55cff'},
};
const EASE = [.2, .8, .2, 1];
const LANES = [90, 190, 290, 390];
const ranked = (scores) => [...scores].sort((a,b) => b.score-a.score || ORDER.indexOf(a.key)-ORDER.indexOf(b.key));
const uniqueLeader = (scores) => {
  const placed = ranked(scores);
  return placed[0]?.score > 0 && placed[0].score > (placed[1]?.score || 0) ? placed[0].key : null;
};
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
  const previewPlayer = data.rewindPreviewPlayer;
  const reduce = useReducedMotion();
  const weeks = recap.weeklyGameScores || [];
  const [week, setWeek] = useState(0);
  const [phase, setPhase] = useState('intro');
  const [playing, setPlaying] = useState(false);
  const [shareStatus, setShareStatus] = useState('');
  const [compact, setCompact] = useState(() => typeof window !== 'undefined' && window.matchMedia('(max-width: 760px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 760px)');
    const update = () => setCompact(mq.matches);
    mq.addEventListener?.('change', update);
    update();
    return () => mq.removeEventListener?.('change', update);
  }, []);
  const discovery = useMemo(()=>filmDiscovery(weeks,recap.gamesPlayed),[weeks,recap.gamesPlayed]);
  const insights = recap.insights || {};
  const style = insights.playStyle || {title:'THE NEXT CHAPTER', evidence:'Your story is only beginning.'};
  const trophy = recap.badges?.featured;
  const completionCount = recap.gamesPlayed || 0;
  const momentum = insights.momentum;
  const secondInsight = style.title === 'THE MAINSTAY' || style.title === 'THE FINISHER'
    ? (insights.highestGame ? 'Your biggest single game: ' + insights.highestGame.score + ' points in ' + insights.highestGame.game + '.' : '')
    : momentum && momentum.direction === 'up'
    ? 'And you finished stronger: your average rose by ' + momentum.change + ' points per game.'
    : momentum && momentum.direction === 'down'
      ? 'Your second-half average dipped by ' + Math.abs(momentum.change) + ' points. Season Two is your comeback.'
      : insights.longestWeeklyStreak >= 2
        ? 'You played across ' + insights.longestWeeklyStreak + ' consecutive weeks.'
        : insights.highestGame
          ? 'Your biggest single game: ' + insights.highestGame.score + ' points in ' + insights.highestGame.game + '.'
          : '';
  const rankText = recap.champion ? 'Season champion' : recap.rank ? 'Ranked #' + recap.rank : 'An original CREW player';
  const scores = useMemo(()=>SUM(weeks,week),[weeks,week]);
  const ranking = ranked(scores);
  const screenLanes = compact ? [53, 155, 257, 359] : LANES;
  const rankingY = Object.fromEntries(ranking.map((item,i)=>[item.key, screenLanes[i]]));
  const liveLeader = uniqueLeader(scores);
  const previousLeader = week > 0 ? uniqueLeader(SUM(weeks,week-1)) : null;
  const leadChanged = !!liveLeader && !!previousLeader && liveLeader !== previousLeader;
  const weekName = weeks[week]?.number || week+1;
  const maximum = Math.max(1,...SUM(weeks,weeks.length-1).map(g=>g.score));
  const lead = discovery.leaders[0]?.key;
  const singleLeader = discovery.leaders.length === 1;
  // Do not spoil the final winner in the first seconds of the film.
  const theme = GAMES[phase==='discovery' ? lead : phase==='race' ? liveLeader : null]?.color || (phase==='trophy' ? '#ffbd45' : '#55b9ff');
  const fullWeek = week >= weeks.length - 1;

  useEffect(() => {
    if (!playing || phase !== 'race' || reduce) return undefined;
    const id = setTimeout(()=>{
      if (week >= weeks.length - 1) {
        setPlaying(false);
        setPhase('discovery');
      } else setWeek(old => Math.min(old+1,weeks.length-1));
    }, leadChanged ? 1650 : 1150);
    return () => clearTimeout(id);
  },[week,weeks.length,playing,phase,reduce,leadChanged]);

  function play() {
    if (reduce || !weeks.length || discovery.noGames) {
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
    setShareStatus('');
    setPhase('intro');
  }
  function continueStory() {
    setPlaying(false);
    setPhase(current => current==='discovery' ? 'identity' : current==='identity' ? (trophy?'trophy':'finale') : 'finale');
  }
  async function shareStory() {
    const summary = 'My CREW Rewind S01: ' + style.title + '. ' + style.evidence +
      ' ' + (recap.points || 0) + ' points, ' + completionCount + ' games and ' +
      (recap.badges?.count || 0) + ' earned badges. #CREWRewind';
    try {
      if (navigator.share) {
        await navigator.share({title:'My CREW Season 01',text:summary});
        setShareStatus('Shared!');
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(summary);
        setShareStatus('Season story copied.');
      } else setShareStatus('Sharing is unavailable in this browser.');
    } catch(error) {
      if (error?.name!=='AbortError') setShareStatus('Sharing is unavailable.');
    }
  }

  const filmTitle = discovery.noGames
    ? 'Your next chapter is unwritten.'
    : !singleLeader
      ? 'A dead heat at the finish.'
      : GAMES[lead].name + ' finished in front.';
  const revealName = discovery.noGames ? 'Season Two awaits'
    : discovery.leaders.map(g=>GAMES[g.key].name).join(' + ');
  const detail = discovery.noGames
    ? 'There are no completed games in this season to compare yet.'
    : singleLeader
      ? GAMES[lead].name + ' earned ' + discovery.topScore + ' of your ' + discovery.total + ' season points.'
      : 'Each of these games earned ' + discovery.topScore + ' points. Your season had a shared lead.';

  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user">
    <main className={'rewind-film rewind-film-' + phase} style={{'--film-accent':theme}}
      aria-label="Experimental Season One interactive film">
      <div className="rewind-film-atmosphere" aria-hidden="true"/>
      <header className="rewind-film-header">
        <span className="rewind-film-mark">CREW<span>+</span><small>REWIND · 01</small></span>
        <span className="rewind-film-preview">{previewPlayer ? "VIEWING " + previewPlayer + " · PRIVATE PREVIEW" : "PRIVATE PREVIEW"}</span>
        <a href="/rewind?preview=1" className="rewind-film-exit" aria-label="Return to the original Rewind">✕</a>
      </header>

      <section className="rewind-film-field">
        <div className="rewind-film-narration" aria-live="polite">
          <m.p className="rewind-film-introline" animate={{opacity:1}} initial={false}>
            {phase==='intro' ? (recap.username || 'YOUR') + ', THIS WAS YOUR SEASON.'
              : phase==='race' ? 'WEEK '+String(weekName).padStart(2,'0')+' / '+String(weeks.length).padStart(2,'0') : phase==='discovery' ? 'YOUR SIGNATURE GAME' : phase==='identity' ? 'THE PLAYER BEHIND THE POINTS' : phase==='trophy' ? 'WHAT YOU EARNED' : 'SEASON 01 · YOUR STORY'}
          </m.p>
          <m.h1 layout animate={{opacity:1}} transition={{duration:reduce?0:.5}}>
            {phase === 'intro' ? (discovery.noGames ? <>The story<br/><em>starts with you.</em></> : <>Your season<br/><em>had a story.</em></>)
              : phase === 'race' ? (leadChanged ? <>Plot twist.<br/><em>{GAMES[liveLeader].name} takes over.</em></>
                : liveLeader ? <>{GAMES[liveLeader].name}<br/><em>leads the way.</em></>
                : <>The race<br/><em>is wide open.</em></>)
              : phase==='discovery' ? filmTitle
              : phase==='identity' ? (discovery.noGames ? <>Your next<br/><em>chapter awaits.</em></> : <>You had<br/><em>your own rhythm.</em></>)
              : phase==='trophy' ? <>Every mark<br/><em>was earned.</em></>
              : <>That was<br/><em>your Season 01.</em></>}
          </m.h1>
        </div>

        <div className={'rewind-film-arena rewind-film-arena-' + phase}>
          <svg viewBox={compact ? '0 0 430 440' : '0 0 940 480'} preserveAspectRatio="xMidYMid meet"
            aria-hidden={phase==='intro' || phase==='identity' || phase==='trophy' || phase==='finale' ? true : undefined}
            role="img" aria-label={phase==='intro' ? 'Four CREW games ready to reveal the season' : 'Cumulative scores through week '+(week+1)+': '+
              scores.map(g=>GAMES[g.key].name+' '+g.score+' points').join(', ')}>
            <defs>
              {ORDER.map(key=><linearGradient id={'film-stream-'+key} key={key} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={GAMES[key].color} stopOpacity="0"/>
                <stop offset="62%" stopColor={GAMES[key].color} stopOpacity=".35"/>
                <stop offset="100%" stopColor={GAMES[key].color} stopOpacity=".9"/>
              </linearGradient>)}
            </defs>
            {scores.map((game,index)=>{
              const y=screenLanes[index];
              const x=(compact ? 65 : 140)+Math.round((game.score/maximum)*(compact ? 252 : 600));
              const introX=(compact ? [62,164,266,368] : [125,355,585,815])[index];
              const introY=compact ? 197 : 240;
              const isLeader=discovery.leaders.some(item=>item.key===game.key);
              const spotlightIndex=discovery.leaders.findIndex(item=>item.key===game.key);
              const targetX=phase==='discovery' && isLeader ? (compact ? 215 : 490) : phase==='intro' ? introX : x;
              const targetY=phase==='discovery' && isLeader
                ? (compact ? 214 : 220) + (spotlightIndex-(discovery.leaders.length-1)/2)*(compact ? 74 : 82)
                : phase==='intro' ? introY : rankingY[game.key];
              const faded=(phase==='discovery' && !isLeader) || ['identity','trophy','finale'].includes(phase);
              const leadingNow=phase==='race' && liveLeader===game.key;
              const spotlightRadius=discovery.leaders.length>1?38:64;
              const radius=phase==='intro' ? (compact?30:47) : phase==='discovery' && isLeader?spotlightRadius:leadingNow?34:25;
              const startX=compact ? 27 : 82;
              const duration=reduce?0:.85;
              return <g key={game.key} className={'rewind-film-contender rewind-film-contender-'+game.key}>
                <m.path d={'M '+startX+' '+y+' C '+(startX+8+x*.22)+' '+(y-44)+' '+(x-65)+' '+(y+24)+' '+x+' '+y}
                  fill="none" stroke={'url(#film-stream-'+game.key+')'} strokeWidth="5" strokeLinecap="round"
                  initial={false} animate={{opacity:phase==='intro' || phase==='identity' || phase==='trophy' || phase==='finale' ? 0 : phase==='discovery' ? .06 : .9,
                    d:'M '+startX+' '+y+' C '+(startX+8+targetX*.22)+' '+(y-44)+' '+(targetX-65)+' '+(y+24)+' '+targetX+' '+targetY}}
                  transition={{duration,ease:EASE}}/>
                <m.circle initial={false} animate={{cx:targetX,cy:targetY,r:radius+13,opacity:leadingNow || (phase==='discovery' && isLeader) ? .3 : 0}}
                  transition={{duration,ease:EASE}} fill="none" stroke={GAMES[game.key].color} strokeWidth="1.5"/>
                <m.circle initial={false} animate={{cx:targetX,cy:targetY,r:radius,opacity:faded?0:1}}
                  transition={{duration,ease:EASE}} fill="#061725" stroke={GAMES[game.key].color}
                  strokeWidth={isLeader || leadingNow ? 3 : 2}/>
                <m.text initial={false}
                  animate={{x:targetX,y:targetY+(phase==='discovery'&&isLeader&&discovery.leaders.length===1?22:10),opacity:faded?0:1,fontSize:phase==='discovery'&&isLeader?(discovery.leaders.length===1?70:42):phase==='intro'? (compact?30:48) : leadingNow?34:28}}
                  transition={{duration,ease:EASE}}
                  textAnchor="middle" fontWeight="900" fill={GAMES[game.key].color}>
                  {GAMES[game.key].symbol}
                </m.text>
                <text x={targetX} y={targetY+(phase==='intro'?(compact?62:83):phase==='discovery'?(compact?72:94):compact?56:60)}
                  opacity={faded?0:phase==='intro'?1:.92}
                  textAnchor="middle" fontSize={phase==='intro'?(compact?20:22):phase==='discovery'?20:compact?18:20}
                  fill="#e2f4ff" fontWeight="800">
                  {GAMES[game.key].name}
                </text>
              </g>;
            })}
          </svg>
          {phase==='identity' && <m.div key="identity" className="rewind-film-personality" initial={reduce?false:{opacity:0,scale:.83,rotate:-3}} animate={{opacity:1,scale:1,rotate:0}} transition={{duration:reduce?0:.8,ease:EASE}}>
            <span>YOUR PLAY STYLE</span>
            <strong>{style.title.replace(/^THE /,'')}</strong>
            <i aria-hidden="true">✳</i>
          </m.div>}
          {phase==='trophy' && trophy && <m.div key="trophy" className="rewind-film-award" initial={reduce?false:{opacity:0,scale:.55,rotate:-12}} animate={{opacity:1,scale:1,rotate:0}} transition={{duration:reduce?0:.9,ease:EASE}}>
            <BadgeMedallion badge={trophy} size="normal" seasonNumber={1}/>
            <span className="rewind-film-award-name">{trophy.name}</span>
            <small className="rewind-film-award-meta">{trophy.rarity} · SEASON 01</small>
          </m.div>}
          {phase==='finale' && <m.div key="finale" className="rewind-film-finale-object" initial={reduce?false:{opacity:0,scale:.9}} animate={{opacity:1,scale:1}} transition={{duration:reduce?0:.8,ease:EASE}}>
            <span>CREW / SEASON 01</span>
            <strong>{recap.username}</strong>
            <em>{style.title}</em>
            <small>{rankText} · {completionCount} {completionCount===1?'game':'games'} played</small>
          </m.div>}
        </div>

        <div className="rewind-film-insight" aria-live="polite">
          {phase==='intro' ? <p>Discover what six weeks of playing revealed about you.</p>
            : phase==='race' ? <p>{leadChanged ? 'The lead just changed.' : liveLeader ? GAMES[liveLeader].name+' is out front.' : 'There is no clear leader this week.'}</p>
            : phase==='discovery' ? <div className="rewind-film-discovery-copy">
                <span>YOUR POINTS LEADER</span>
                <h2>{revealName}</h2>
                {!discovery.noGames && <m.strong className="rewind-film-impact" initial={reduce ? false : {opacity:0, y:14}} animate={{opacity:1,y:0}} transition={{duration:reduce?0:.6,delay:reduce?0:.25}}>{discovery.percent}%</m.strong>}
                {!discovery.noGames && <span className="rewind-film-impact-label">OF YOUR SEASON POINTS {singleLeader ? 'CAME FROM THIS GAME' : 'CAME FROM EACH TIED GAME'}</span>}
                <p>{detail}</p>
                {discovery.leadChanges>0 && <p className="rewind-film-twist">The lead changed {discovery.leadChanges} {discovery.leadChanges===1?'time':'times'} along the way.</p>}
                {singleLeader && recap.signature?.key && recap.signature.key!==lead &&
                  <p className="rewind-film-twist">The twist: {GAMES[recap.signature.key].name} had your highest average score per game.</p>}
              </div> : phase==='identity' ? <div className="rewind-film-story-beat">
                <p>{style.evidence}</p>
                {secondInsight && secondInsight!==style.evidence && <p>{secondInsight}</p>}
              </div> : phase==='trophy' ? <div className="rewind-film-story-beat">
                <p>{recap.badges?.count === 1 ? 'One badge. A moment you earned.' : recap.badges?.count + ' earned badges. This one leads your collection.'}</p>
              </div> : <div className="rewind-film-story-beat rewind-film-finale-copy">
                <p>{style.evidence}</p>
                <p>{recap.champion ? 'You finished as Season 01 champion.' : recap.rank ? 'You earned a place on the Season 01 leaderboard.' : 'Your journey as one of the original CREW players has begun.'}</p>
                {shareStatus && <span role="status">{shareStatus}</span>}
              </div>}
        </div>
      </section>

      <footer className="rewind-film-controls">
        <div className="rewind-film-timeline" hidden={phase!=='race'} role="group" aria-label="Select a week in the season">
          {weeks.map((row,i)=><button type="button" key={row.number} onClick={()=>chooseWeek(i)}
            aria-current={phase==='race'&&week===i?'step':undefined}
            aria-label={'See week '+row.number+' results'}><span>{String(row.number).padStart(2,'0')}</span></button>)}
        </div>
        <div className="rewind-film-buttons">
          {phase==='intro' ? <button className="rewind-film-primary" type="button" onClick={play}>Play my season <span aria-hidden="true">→</span></button>
            : phase==='race' ? <>
              <button type="button" onClick={()=>setPlaying(v=>!v)} disabled={!!reduce}>{playing?'Pause':'Play'} <span aria-hidden="true">{playing?'Ⅱ':'▶'}</span></button>
              <button className="rewind-film-primary" type="button" onClick={reveal}>Discover my pattern <span aria-hidden="true">→</span></button>
            </> : phase==='discovery' ? <button className="rewind-film-primary" type="button" onClick={continueStory}>But that's only part of the story →</button>
            : phase==='identity' ? <button className="rewind-film-primary" type="button" onClick={continueStory}>{trophy?'See what you earned':'Your season, remembered'} →</button>
            : phase==='trophy' ? <button className="rewind-film-primary" type="button" onClick={continueStory}>Finish my story →</button>
            : <><button type="button" onClick={replay}>Watch again ↺</button>{!previewPlayer && <button className="rewind-film-primary" type="button" onClick={shareStory}>Share my season ↗</button>}</>}
        </div>
      </footer>
    </main>
  </MotionConfig></LazyMotion>;
}

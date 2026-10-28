import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, LazyMotion, MotionConfig, animate, domAnimation, m, useReducedMotion } from 'motion/react';
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

const mix = (from, to, fraction) => from + (to-from)*fraction;
const easeAcross = value => value*value*(3-2*value);

// Scores, horizontal motion, and rank changes share one continuous 0..N-1
// timeline. Scrubbing, pausing, and resuming preserve the exact same frame.
export function filmFrame(weeks, progress, lanes) {
  if (!weeks.length) return ORDER.map((key, index) => ({key, score:0, y:lanes[index]}));
  const lower = Math.max(0, Math.min(weeks.length-1, Math.floor(progress)));
  const upper = Math.min(weeks.length-1,lower+1);
  const t = Math.max(0,Math.min(1,progress-lower));
  const a=SUM(weeks,lower), b=SUM(weeks,upper);
  const orderedA=ranked(a), orderedB=ranked(b);
  return ORDER.map(key=>{
    const first=orderedA.findIndex(g=>g.key===key);
    const next=orderedB.findIndex(g=>g.key===key);
    return {
      key,
      score:mix(a.find(g=>g.key===key).score,b.find(g=>g.key===key).score,t),
      y:mix(lanes[first],lanes[next],easeAcross(t)),
    };
  });
}

// Descriptive insights for every week, computed from the SAME cutoff-filtered
// scores as the animation. Never imply zero points means a completed game.
export function filmWeekBeat(weeks, index) {
  const row=weeks[index];
  if (!row) return {title:'The season begins.', detail:'Every point tells part of the story.'};
  const entries=ORDER.map(key=>({key,points:Number(row.games?.[key])||0}));
  const total=entries.reduce((sum,g)=>sum+g.points,0);
  const types=entries.filter(g=>g.points>0).length;
  if (!total) return {title:'A quieter week.',detail:'No points were recorded this week. Your running total held steady.'};
  const previous=index>0 ? uniqueLeader(SUM(weeks,index-1)) : null;
  const unique=uniqueLeader(SUM(weeks,index));
  const top=entries.sort((a,b)=>b.points-a.points||ORDER.indexOf(a.key)-ORDER.indexOf(b.key))[0];
  const previousMax=Math.max(0,...weeks.slice(0,index).map(w=>ORDER.reduce((s,key)=>s+(Number(w.games?.[key])||0),0)));
  const topShare=Math.round(100*top.points/total);
  const seasonRanking=ranked(SUM(weeks,index));
  const margin=(seasonRanking[0]?.score||0)-(seasonRanking[1]?.score||0);
  if (previous && unique && previous!==unique)
    return {title:'The lead changed.',detail:GAMES[unique].name+' took the cumulative lead by '+margin+' points after a '+total+'-point week.'};
  if (index>0 && total>previousMax)
    return {title:'A new weekly high.',detail:'You earned '+total+' points in week '+row.number+' — '+(total-previousMax)+' more than your previous best week.'};
  if (types>=3)
    return {title:'You covered your bases.',detail:'You scored in '+types+' game types. '+GAMES[top.key].name+' delivered '+topShare+'% of your '+total+' weekly points.'};
  if (top.points>0)
    return {title:GAMES[top.key].name+' had its moment.',detail:GAMES[top.key].name+' contributed '+topShare+'% of this week’s points ('+top.points+' of '+total+').'};
  return {title:'Another week in the books.',detail:total+' points added to your season.'};
}

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
  const [progress, setProgress] = useState(0);
  const progressRef = useRef(0);
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
  const personalFindings = [
    momentum && momentum.direction !== 'steady' && style.title !== 'THE FINISHER'
      ? (momentum.direction === 'up'
          ? 'Your later games averaged '+momentum.change+' more points than your earlier games.'
          : 'Your later games averaged '+Math.abs(momentum.change)+' fewer points—your next comeback awaits.')
      : null,
    insights.longestWeeklyStreak>=2 && style.title !== 'THE MAINSTAY'
      ? 'You completed games in '+insights.longestWeeklyStreak+' consecutive season weeks.' : null,
    insights.highestGame
      ? 'Your biggest single game was '+insights.highestGame.score+' points in '+insights.highestGame.game+'.' : null,
    insights.outpacedPercent!=null && recap.participants>1
      ? 'You outscored '+insights.outpacedPercent+'% of the other active players.' : null,
  ].filter(Boolean).filter(fact=>fact!==style.evidence).slice(0,2);
  const rankText = recap.champion ? 'Season champion' : recap.rank ? 'Ranked #' + recap.rank : 'An original CREW player';
  const week = Math.min(Math.max(0,weeks.length-1),Math.floor(progress+1e-5));
  const screenLanes = compact ? [53, 155, 257, 359] : LANES;
  const scores = filmFrame(weeks,progress,screenLanes);
  const scoreSnapshot = useMemo(()=>SUM(weeks,week),[weeks,week]);
  const runningPoints=Math.round(scores.reduce((sum,game)=>sum+game.score,0));
  const weekPoints=useMemo(()=>ORDER.reduce((sum,key)=>sum+(Number(weeks[week]?.games?.[key])||0),0),[weeks,week]);
  const rankingY = Object.fromEntries(scores.map(g=>[g.key,g.y]));
  const liveLeader = uniqueLeader(scores);
  const weekBeat = useMemo(()=>filmWeekBeat(weeks,week),[weeks,week]);
  const weekName = weeks[week]?.number || week+1;
  const maximum = Math.max(1,...SUM(weeks,weeks.length-1).map(g=>g.score));
  const lead = discovery.leaders[0]?.key;
  const singleLeader = discovery.leaders.length === 1;
  // Do not spoil the final winner in the first seconds of the film.
  const theme = GAMES[phase==='discovery' ? lead : phase==='race' ? liveLeader : null]?.color || (phase==='trophy' ? '#ffbd45' : '#55b9ff');
  const fullWeek = progress >= weeks.length-1;

  useEffect(() => {
    if (!playing || phase !== 'race' || reduce) return undefined;
    const from=progressRef.current;
    const end=weeks.length-1;
    if (from>=end) {
      setPlaying(false);
      setPhase('discovery');
      return undefined;
    }
    let revealTimer;
    const controls=animate(from,end,{
      duration:(end-from)*2.15, ease:'linear',
      onUpdate:value=>{
        progressRef.current=value;
        setProgress(value);
      },
      onComplete:()=>{
        progressRef.current=end;
        setProgress(end);
        revealTimer=setTimeout(()=>{
          setPlaying(false);
          setPhase('discovery');
        },850);
      },
    });
    return ()=>{controls.stop();clearTimeout(revealTimer);};
  },[playing,phase,reduce,weeks.length]);

  function seek(value) {
    const clamped=Math.max(0,Math.min(weeks.length-1,value));
    progressRef.current=clamped;
    setProgress(clamped);
  }
  function play() {
    if (reduce || weeks.length<2 || discovery.noGames) {
      seek(Math.max(0,weeks.length-1));
      setPlaying(false);
      setPhase('discovery');
      return;
    }
    if (phase==='intro' || fullWeek) seek(0);
    setPhase('race');
    setPlaying(true);
  }
  function chooseWeek(i) {
    setPlaying(false);
    seek(i);
    setPhase('race');
  }
  function reveal() {
    setPlaying(false);
    seek(Math.max(0,weeks.length-1));
    setPhase('discovery');
  }
  function replay() {
    setPlaying(false);
    seek(0);
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
              : phase==='race' ? 'YOUR SEASON IN MOTION · WEEK '+String(weekName).padStart(2,'0') : phase==='discovery' ? 'YOUR SIGNATURE GAME' : phase==='identity' ? 'THE PLAYER BEHIND THE POINTS' : phase==='trophy' ? 'WHAT YOU EARNED' : 'SEASON 01 · YOUR STORY'}
          </m.p>
          <m.h1 animate={{opacity:1}} transition={{duration:reduce?0:.5}}>
            {phase === 'intro' ? (discovery.noGames ? <>The story<br/><em>starts with you.</em></> : <>Your season<br/><em>had a story.</em></>)
              : phase === 'race' ? <>Your season<br/><em>in motion.</em></>
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
              scoreSnapshot.map(g=>GAMES[g.key].name+' '+g.score+' points').join(', ')}>
            <defs>
              {ORDER.map(key=><linearGradient id={'film-stream-'+key} key={key} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={GAMES[key].color} stopOpacity="0"/>
                <stop offset="62%" stopColor={GAMES[key].color} stopOpacity=".35"/>
                <stop offset="100%" stopColor={GAMES[key].color} stopOpacity=".9"/>
              </linearGradient>)}
            </defs>
            {scores.map((game,index)=>{
              const y=screenLanes[index];
              const x=(compact ? 65 : 140)+(game.score/maximum)*(compact ? 252 : 600);
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
              const duration=reduce||phase==='race'?0:.85;
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
                <m.text initial={false}
                  animate={{x:targetX,y:targetY+(phase==='intro'?(compact?62:83):phase==='discovery'?(compact?72:94):compact?56:60),opacity:faded?0:phase==='intro'?1:.92}}
                  transition={{duration,ease:EASE}}
                  textAnchor="middle" fontSize={phase==='intro'?(compact?20:22):phase==='discovery'?20:compact?18:20}
                  fill="#e2f4ff" fontWeight="800">
                  {GAMES[game.key].name}
                </m.text>
                <m.text className="rewind-film-race-score" initial={false}
                  animate={{x:targetX+radius+(compact?9:13),y:targetY+6,opacity:phase==='race'?1:0}}
                  transition={{duration,ease:EASE}}
                  textAnchor="start" fontSize={compact?16:20} fontWeight="900"
                  fill="#f1f8ff" aria-hidden="true">
                  {Math.round(game.score).toLocaleString()}
                </m.text>
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

        <div className={'rewind-film-insight'+(phase==='race'?' rewind-film-insight-race':'')} aria-live="polite">
          {phase==='intro' ? <p>Discover what six weeks of playing revealed about you.</p>
            : phase==='race' ? <div className="rewind-film-race-report">
                <div className="rewind-film-race-copy">
                  <span className="rewind-film-finding-label">WEEK {String(weekName).padStart(2,'0')} · {weekBeat.title} · {weekPoints} PTS THIS WEEK</span>
                  <AnimatePresence mode="wait" initial={false}>
                    <m.p key={'week-insight-'+week} className="rewind-film-week-finding"
                      initial={reduce?false:{opacity:0,y:9}} animate={{opacity:1,y:0}}
                      exit={reduce?undefined:{opacity:0,y:-7}} transition={{duration:reduce?0:.23,ease:EASE}}>
                      {weekBeat.detail}
                    </m.p>
                  </AnimatePresence>
                </div>
                <div className="rewind-film-running-total" aria-hidden="true">
                  <strong>{runningPoints.toLocaleString()}</strong><span>SEASON POINTS</span>
                </div>
              </div>
            : phase==='discovery' ? <div className="rewind-film-discovery-copy">
                <span>YOUR POINTS LEADER</span>
                <h2>{revealName}</h2>
                {!discovery.noGames && <m.strong className="rewind-film-impact" initial={reduce ? false : {opacity:0, y:14}} animate={{opacity:1,y:0}} transition={{duration:reduce?0:.6,delay:reduce?0:.25}}>{discovery.percent}%</m.strong>}
                {!discovery.noGames && <span className="rewind-film-impact-label">OF YOUR SEASON POINTS {singleLeader ? 'CAME FROM THIS GAME' : 'CAME FROM EACH TIED GAME'}</span>}
                <p>{detail}</p>
                {discovery.leadChanges>0 && <p className="rewind-film-twist">The lead changed {discovery.leadChanges} {discovery.leadChanges===1?'time':'times'} along the way.</p>}
                {singleLeader && recap.signature?.key && recap.signature.key!==lead &&
                  <p className="rewind-film-twist">The twist: {GAMES[recap.signature.key].name} had your highest average score per game.</p>}
                {insights.peerComparison && <p className="rewind-film-twist">
                  In {insights.peerComparison.game}, you averaged {insights.peerComparison.yourAverage} points versus {insights.peerComparison.crewAverage} across {insights.peerComparison.playersCompared} other players.
                </p>}
              </div> : phase==='identity' ? <div className="rewind-film-story-beat">
                <p>{style.evidence}</p>
                {personalFindings.map((finding,i)=><m.p key={finding} initial={reduce?false:{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{duration:reduce?0:.45,delay:reduce?0:.18+i*.24}}>{finding}</m.p>)}
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
        <div className="rewind-film-timeline" hidden={phase!=='race'} role="group" aria-label="Select a week in the season" style={{'--film-progress':weeks.length>1?(100*progress/(weeks.length-1)).toFixed(1)+'%':'0%'}}>
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

import React from 'react';
import {m} from 'motion/react';

const labelScore = value => Number(value || 0).toLocaleString('en-US', {maximumFractionDigits:1});
const tween = {duration:1.7,ease:[.22,1,.36,1]};

function DataLine({points, color, delay=0}) {
  return <m.polyline points={points} fill="none" stroke={color} strokeWidth="5"
    strokeLinecap="round" strokeLinejoin="round" pathLength="1"
    initial={{pathLength:0,opacity:.3}}
    animate={{pathLength:1,opacity:1}}
    transition={{duration:2.6,delay,ease:[.25,.7,.25,1]}}/>;
}

function SeasonTrajectory({rival, turningWeek}) {
  const weeks=rival.weekly || [];
  if(!weeks.length) return null;
  const series=[{week:0,mine:0,rival:0},...weeks];
  const max=Math.max(1,...series.flatMap(w=>[w.mine,w.rival]));
  const point=(value,i)=>[55+(i/(series.length-1))*550,275-(value/max)*217];
  const build=key=>series.map((w,i)=>point(w[key],i).join(',')).join(' ');
  const endMe=point(series[series.length-1].mine,series.length-1);
  const endPeer=point(series[series.length-1].rival,series.length-1);
  const pivot=Number.isInteger(turningWeek)?Math.max(0,Math.min(weeks.length,turningWeek)):null;
  const pivotX=pivot!==null?point(0,pivot)[0]:null;
  return <div className="rd-trajectory" role="img"
    aria-label={'Cumulative game points across '+weeks.length+' scheduled weeks: you finished on '+rival.myTotal+' and '+rival.name+' on '+rival.theirTotal+'.'}>
    <svg viewBox="0 0 690 340" preserveAspectRatio="xMidYMid meet">
      <defs><linearGradient id="rd-sea-grad" x1="0" y1="0" x2="1" y2="0"><stop stopColor="#80f2df"/><stop offset="1" stopColor="#69c3ff"/></linearGradient></defs>
      {[0,.25,.5,.75,1].map(v=><line key={v} x1="45" x2="635" y1={275-v*217} y2={275-v*217} className="rd-gridline"/>)}
      {pivotX!==null&&<><m.line x1={pivotX} x2={pivotX} y1="45" y2="278" stroke="#e6c186" strokeDasharray="4 8"
          initial={{opacity:0}} animate={{opacity:.65}} transition={{delay:2.2}}/>
        <text x={Math.min(pivotX+8,545)} y="40" fill="#eecb91" fontSize="16" fontWeight="800">WEEK {turningWeek} SHIFT</text></>}
      <DataLine points={build('rival')} color="#df9cce" delay={.22}/>
      <DataLine points={build('mine')} color="url(#rd-sea-grad)" delay={.48}/>
      <m.circle cx={endMe[0]} cy={endMe[1]} r="8" fill="#8cecdf" stroke="#051726" strokeWidth="3"
        initial={{scale:0}} animate={{scale:1}} transition={{delay:2.7}}/>
      <m.circle cx={endPeer[0]} cy={endPeer[1]} r="8" fill="#e4a4d0" stroke="#051726" strokeWidth="3"
        initial={{scale:0}} animate={{scale:1}} transition={{delay:2.45}}/>
      {weeks.map((w,i)=><text key={w.week} x={point(0,i+1)[0]} y="313" textAnchor="middle" fill="#a3b5c7" fontSize="13">W{w.week}</text>)}
    </svg>
    <div className="rd-line-legend"><span><i className="rd-key-user"/>YOU · {labelScore(rival.myTotal)}</span><span><i className="rd-key-rival"/>{rival.name} · {labelScore(rival.theirTotal)}</span></div>
    <div className="rd-micro">SCHEDULED GAME WEEKS · NOT REAL-TIME SUBMISSION ORDER</div>
  </div>;
}

function FinishLine({rival}) {
  const biggest=Math.max(1,rival.myTotal,rival.theirTotal);
  const difference=Math.abs(rival.difference);
  return <div className="rd-finish">
    <div className="rd-finish-headline">
      <div><span>YOUR SEASON</span><m.strong initial={{opacity:0,y:28}} animate={{opacity:1,y:0}} transition={tween}>{labelScore(rival.myTotal)}</m.strong></div>
      <div className="rd-finish-divider" aria-hidden="true"/>
      <div><span>{rival.name}</span><m.strong initial={{opacity:0,y:28}} animate={{opacity:1,y:0}} transition={{...tween,delay:.25}}>{labelScore(rival.theirTotal)}</m.strong></div>
    </div>
    <div className="rd-finish-ribbon" aria-hidden="true"><m.span initial={{scaleX:0}} animate={{scaleX:rival.myTotal/biggest}} transition={{duration:1.9}}/><m.span initial={{scaleX:0}} animate={{scaleX:rival.theirTotal/biggest}} transition={{duration:2,delay:.3}}/></div>
    <p>THE DIFFERENCE <strong>{labelScore(difference)} POINTS</strong></p>
  </div>;
}

function SwingBalance({visual}) {
  const max=Math.max(1,Math.abs(visual.edge||0),Math.abs(visual.other||0));
  return <div className="rd-swing" role="img" aria-label={'Your '+visual.game+' advantage '+visual.edge+', other games '+visual.other+', net '+visual.net+' points'}>
    <div className="rd-swing-label">THE GAME THAT TILTED THE SEASON</div>
    <div className="rd-swing-row rd-swing-positive"><span>{visual.game}</span><strong>+{labelScore(visual.edge)}</strong><div className="rd-swing-rail"><m.i initial={{scaleX:0}} animate={{scaleX:Math.abs(visual.edge)/max}} transition={{duration:1.65}}/></div></div>
    <div className="rd-swing-row rd-swing-negative"><span>ALL OTHER GAMES</span><strong>{visual.other>0?'+':''}{labelScore(visual.other)}</strong><div className="rd-swing-rail"><m.i initial={{scaleX:0}} animate={{scaleX:Math.abs(visual.other)/max}} transition={{duration:1.8,delay:.25}}/></div></div>
    <div className="rd-swing-net"><span>SEASON MARGIN</span><m.strong initial={{opacity:0,scale:.7}} animate={{opacity:1,scale:1}} transition={{delay:1.4,...tween}}>{visual.net>0?'+':''}{labelScore(visual.net)}</m.strong></div>
    <p className="rd-micro">TOTAL POINT CONTRIBUTIONS · NOT PER-ATTEMPT GAME SKILL</p>
  </div>;
}

function RankCounterfactual({beat,recap}) {
  const visual=beat.visual || {};
  const change=parseInt(beat.metric,10);
  const next=Number.isFinite(change)&&visual.currentRank?visual.currentRank+change:null;
  return <div className="rd-ranks" aria-label="Hypothetical standings without this week">
    <div className="rd-ranks-slot"><span>{recap.finalized?'FINAL RANK':'PREVIEW RANK'}</span><m.strong initial={{opacity:0,x:-35}} animate={{opacity:1,x:0}} transition={tween}>#{visual.currentRank||'—'}</m.strong></div>
    <div className="rd-ranks-arrow" aria-hidden="true"><svg viewBox="0 0 120 80"><path d="M4 40 H108 M79 13 L108 40 L79 67" stroke="#f6ce85" strokeWidth="3" fill="none"/></svg></div>
    <div className="rd-ranks-slot"><span>WITHOUT THAT WEEK</span><m.strong initial={{opacity:0,x:35}} animate={{opacity:1,x:0}} transition={{...tween,delay:.5}}>{next?'#'+next:'—'}</m.strong></div>
    <p className="rd-micro">HYPOTHETICAL FINAL RANK · NOT A HISTORICAL LEADERBOARD</p>
  </div>;
}

function StrengthComparison({visual}) {
  if(!Number.isFinite(Number(visual.mine))||!Number.isFinite(Number(visual.peers))) return null;
  const max=Math.max(1,visual.mine,visual.peers);
  return <div className="rd-strength" role="img" aria-label={'Your '+visual.game+' average '+visual.mine+' points, other players average '+visual.peers}>
    <div className="rd-strength-columns">
      {[{label:'YOU',score:visual.mine},{label:'THE FIELD',score:visual.peers}].map((d,i)=><div className={'rd-strength-column rd-strength-'+i} key={d.label}>
        <strong>{labelScore(d.score)}</strong>
        <div className="rd-strength-rail"><m.div initial={{scaleY:0}} animate={{scaleY:Math.max(.05,d.score/max)}} transition={{duration:1.8,delay:i*.22}}/></div>
        <span>{d.label}</span>
      </div>)}
    </div>
    <p>{visual.game} · AVERAGE POINTS PER COMPLETED GAME</p>
    <div className="rd-micro">{visual.ownAttempts} PERSONAL GAMES · {visual.otherPlayers} OTHER PLAYERS</div>
  </div>;
}

function StandoutConstellation({visual}) {
  const peers=Math.min(Math.max(Number(visual.peerCount)||0,0),40);
  if(!peers) return null;
  const wins=Number(visual.outscored)||0;
  return <div className="rd-constellation" aria-label={wins+' out of '+peers+' other players outscored on the same puzzle'}>
    <div className="rd-constellation-core"><span>YOUR SCORE</span><strong>{labelScore(visual.score)}</strong></div>
    <div className="rd-constellation-peers">{Array.from({length:peers},(_,i)=><m.i key={i} className={i<wins?'rd-won':'rd-tied'} initial={{opacity:0,scale:.2}} animate={{opacity:1,scale:1}} transition={{delay:.35+i*.08,duration:.5}}/>)}</div>
    <p>PEER MEDIAN <strong>{labelScore(visual.peerMedian)}</strong></p>
  </div>;
}

function ConsistencyRhythm({recap}) {
  return <div className="rd-rhythm" aria-label="Games completed across scheduled weeks">
    {(recap.weeklyScores||[]).map((w,i)=><div className="rd-rhythm-week" key={w.number}>
      <m.div initial={{scaleY:0}} animate={{scaleY:1}} transition={{duration:.7,delay:i*.13}} className={w.played?'rd-rhythm-active':'rd-rhythm-idle'} style={{height:(w.played?Math.min(100,18+w.played*19):9)+'%'}}/>
      <span>W{w.number}</span>
    </div>)}
    <p className="rd-micro">EACH COLUMN = ONE SCHEDULED WEEK · HEIGHT REPRESENTS GAMES COMPLETED</p>
  </div>;
}

function MomentumSignal({beat}) {
  const negative=String(beat.metric).startsWith('-');
  return <div className="rd-momentum" role="img" aria-label={'Directional half-season change: '+beat.metric}>
    <div className="rd-momentum-end"><span>EARLIER</span><i/></div>
    <svg viewBox="0 0 520 210" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <path d={negative?'M20 33 C180 30 280 185 500 177':'M20 177 C190 185 320 20 500 33'}
        fill="none" stroke="#f6b7cb" strokeWidth="5" strokeLinecap="round" strokeDasharray="7 12" opacity=".2"/>
      <m.path d={negative?'M20 33 C180 30 280 185 500 177':'M20 177 C190 185 320 20 500 33'}
        fill="none" stroke="#f6b7cb" strokeWidth="5" strokeLinecap="round"
        initial={{pathLength:0}} animate={{pathLength:1}} transition={{duration:2.4}}/>
    </svg>
    <div className="rd-momentum-end"><span>LATER</span><i/></div>
    <p className="rd-micro">DIRECTIONAL ILLUSTRATION · SAME GAME TYPES IN BOTH HALVES</p>
  </div>;
}

function CosmicSeal({beat,recap}) {
  return <div className="rd-seal" aria-hidden="true">
    <m.div className="rd-seal-ring rd-seal-ring-one" initial={{rotate:-45,opacity:0}} animate={{rotate:360,opacity:.75}} transition={{duration:22,ease:'linear',repeat:Infinity}}/>
    <m.div className="rd-seal-ring rd-seal-ring-two" initial={{rotate:75,opacity:0}} animate={{rotate:-360,opacity:.6}} transition={{duration:30,ease:'linear',repeat:Infinity}}/>
    <div className="rd-seal-core"><span>{beat.kind==='ending'?'S01':recap.seasonNumber?'S0'+recap.seasonNumber:'CREW'}</span><strong>{beat.kind==='ending'?'✳':'✦'}</strong></div>
  </div>;
}

export default function RewindDirectorScenes({beat,recap}) {
  const visual=beat.visual||{};
  if(beat.kind==='trajectory' && visual.rival) return <SeasonTrajectory rival={visual.rival} turningWeek={visual.turningWeek}/>;
  if(beat.kind==='rivalry' && visual.rival) return <FinishLine rival={visual.rival}/>;
  if(beat.kind==='swing') return <SwingBalance visual={visual}/>;
  if(beat.kind==='pivot') return <RankCounterfactual beat={beat} recap={recap}/>;
  if(beat.kind==='strength' && visual.mine!==undefined) return <StrengthComparison visual={visual}/>;
  if(beat.kind==='standout' && visual.peerCount) return <StandoutConstellation visual={visual}/>;
  if(beat.kind==='consistency') return <ConsistencyRhythm recap={recap}/>;
  if(beat.kind==='momentum') return <MomentumSignal beat={beat}/>;
  return <CosmicSeal beat={beat} recap={recap}/>;
}

import React from 'react';
import {m} from 'motion/react';
import {BadgeMedallion} from './TrophyRoom';

const KEYS={mystery:'var(--crew-game-mystery,#55e6ac)',trivia:'var(--crew-game-trivia,#ffbd45)',word:'var(--crew-game-word,#55b9ff)',tick_tock:'var(--crew-game-tick-tock,#c55cff)'};
const num=n=>Number(n||0).toLocaleString('en-US',{maximumFractionDigits:1});
const reveal={duration:1.15,ease:[.22,1,.36,1]};
function Badge({item,size='large'}){
  return <div className={'saga-badge saga-badge-'+size}>
    <BadgeMedallion badge={item} size={size==='large'?'normal':'compact'} seasonNumber={1}/>
    <strong>{item.name}</strong><small>{item.rarity?.toUpperCase()}</small>
  </div>;
}
function Center({label,title,value,children}){
  return <div className="saga-center"><span className="saga-kicker">{label}</span>
    {value!==undefined&&<m.strong className="saga-huge" initial={{scale:.65,opacity:0}} animate={{scale:1,opacity:1}} transition={reveal}>{value}</m.strong>}
    <h1>{title}</h1>{children}</div>;
}
function WeekLines({weeks,bestWeek,reduce}){
  const max=Math.max(1,...weeks.map(w=>w.highest));
  const at=(w,i,key)=>[(i/(Math.max(1,weeks.length-1)))*780+30,250-(w[key]/max)*195];
  const points=key=>weeks.map((w,i)=>at(w,i,key).join(',')).join(' ');
  return <div className="saga-chart" role="img" aria-label="Animated weekly player score compared with highest CREW player score">
    <svg viewBox="0 0 840 315" preserveAspectRatio="xMidYMid meet">
      {[0,.25,.5,.75,1].map(v=><line key={v} x1="30" x2="810" y1={250-195*v} y2={250-195*v} stroke="#617080" strokeOpacity=".21"/>)}
      <m.polyline points={points('highest')} fill="none" stroke="var(--crew-game-trivia,#ffbd45)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" initial={reduce?false:{pathLength:0}} animate={{pathLength:1}} transition={{duration:2.2}}/>
      <m.polyline points={points('mine')} fill="none" stroke="var(--crew-game-word,#55b9ff)" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" initial={reduce?false:{pathLength:0}} animate={{pathLength:1}} transition={{duration:2.6,delay:.4}}/>
      {weeks.map((w,i)=><g key={w.week}>
        <m.circle cx={at(w,i,'mine')[0]} cy={at(w,i,'mine')[1]} r={w.week===bestWeek?9:5} fill="var(--crew-game-word,#55b9ff)" initial={reduce?false:{scale:0}} animate={{scale:1}} transition={{delay:.8+i*.28}}/>
        <text x={at(w,i,'mine')[0]} y="288" textAnchor="middle" fill="#adc3d7" fontSize="17">W{w.week}</text>
      </g>)}
    </svg>
    <div className="saga-chart-legend"><span><i style={{background:KEYS.word}}/>YOUR SCORE</span><span><i style={{background:KEYS.trivia}}/>WEEKLY HIGHEST</span></div>
  </div>;
}
function Compare({games}){
 return <div className="saga-comparisons">{games.map(g=><div key={g.key} className="saga-comparison" style={{'--game':KEYS[g.key]}}>
   <strong>{g.name}</strong><div className="saga-double">
     <span>YOU <b>{g.mine===null?'—':num(g.mine)}</b><m.i initial={{scaleX:0}} animate={{scaleX:g.mine===null?0:Math.min(1,g.mine/100)}} transition={{duration:1.4}}/></span>
     <span>CREW <b>{g.crew===null?'—':num(g.crew)}</b><m.i initial={{scaleX:0}} animate={{scaleX:g.crew===null?0:Math.min(1,g.crew/100)}} transition={{duration:1.5,delay:.18}}/></span>
   </div><small>{g.mine===null?'No completed games':g.crew===null?'No other players to compare':g.mine>g.crew?'ABOVE CREW AVERAGE':g.mine===g.crew?'MATCHED CREW AVERAGE':'BELOW CREW AVERAGE'}</small>
 </div>)}</div>;
}
function GameDna({games,totalPoints}){
 const ring=(key)=><div className="saga-dna-ring" style={{background:'conic-gradient('+games.reduce((a,g)=>{const n=key==='gameShare'?g.gameShare:g.pointShare;return a+(a?',':'')+KEYS[g.key]+' '+(a.start||0)+'% '+n+'%';},'')+')'}}/>;
 // Animated compositional distribution: individual segments use the official four game hues.
 const visual=mode=><div className="saga-distribution">
  {games.map(g=><m.div key={g.key} className="saga-distribution-part" title={g.name} style={{background:KEYS[g.key]}}
    initial={{flexGrow:0,opacity:.1}} animate={{flexGrow:mode==='games'?g.gameShare:g.pointShare,opacity:1}}
    transition={{duration:1.4,ease:[.22,1,.36,1]}}/>)}
 </div>;
 return <div className="saga-dna">
   <div><h3>YOUR GAME MIX</h3>{visual('games')}
    <div className="saga-dna-legend">{games.map(g=><span key={g.key} style={{'--game':KEYS[g.key]}}>{g.name}<b>{g.gameShare.toFixed(1)}%</b></span>)}</div>
   </div>
   {totalPoints>0&&<div><h3>WHERE THE POINTS CAME FROM</h3>{visual('points')}
    <div className="saga-dna-legend">{games.map(g=><span key={g.key} style={{'--game':KEYS[g.key]}}>{g.name}<b>{g.pointShare.toFixed(1)}%</b></span>)}</div>
   </div>}
 </div>;
}
function Legacy({v,recap}){
 return <article className="saga-legacy" aria-label="Your Season 01 Legacy card">
 <header><b>CREW GAMES</b><span>SEASON 01</span></header>
 <div className="saga-legacy-body"><span className="saga-kicker">YOUR SEASON LEGACY</span><h1>{v.player}</h1><p>{v.champion?'SEASON CHAMPION':'A SEASON OF YOUR OWN'}</p></div>
 <div className="saga-legacy-stats">{[['FINAL RANK',v.rank?'#'+v.rank:'—'],['POINTS',num(v.points)],['GAMES',v.completed],['PODIUM WEEKS',v.podiumWeeks]].map(([t,n])=><div key={t}><strong>{n}</strong><small>{t}</small></div>)}</div>
 <div className="saga-legacy-foot"><span>{v.signature?'SIGNATURE GAME · '+v.signature:'PART OF THE CREW'}</span>
 {v.badges?.length>0&&<div>{v.badges.map(b=><Badge key={b.code} item={b} size="small"/>)}</div>}</div>
 </article>;
}
export default function RewindSagaScene({beat,recap,reduce}){
 const v=beat.visual||{};
 switch(beat.kind){
  case 'winner':return <div className="saga-winner"><div className="saga-particles" aria-hidden="true">{Array.from({length:22},(_,i)=><i key={i} style={{'--i':i}}/>)}</div><Center label="CREW · SEASON 01" value="✦" title={beat.headline}><p>{v.shared?'A SHARED FIRST PLACE':'YOU LED THE SEASON'}</p></Center></div>;
  case 'winner_badge':return <div className="saga-award"><span className="saga-kicker">THE OFFICIAL BADGE</span><m.div initial={{scale:.4,opacity:0,rotate:-18}} animate={{scale:1,opacity:1,rotate:0}} transition={reveal}><Badge item={v.badge}/></m.div></div>;
  case 'welcome':return <Center label="CREW · SEASON 01" value="01" title={beat.headline}><p>{recap.username}, this story belongs to you.</p></Center>;
  case 'podium':return <Center label="THE PODIUM" value={v.count} title="Times among the weekly Top 3."><div className="saga-podium-weeks">{Array.from({length:v.weeksTotal},(_,i)=>{const w=v.weeks.find(x=>x.week===i+1);return <div key={i}><m.span className={'saga-podium-slot '+(w?'is-earned':'')} initial={{opacity:0,y:15}} animate={{opacity:1,y:0}} transition={{delay:i*.15}}>{w?'#'+w.place:'·'}</m.span><small>W{i+1}</small></div>})}</div><p>#{v.frequencyRank} for weekly podium appearances this season.</p></Center>;
  case 'weekly_trend':return <div className="saga-wide"><h1>{beat.headline}</h1><WeekLines weeks={v.weeks} bestWeek={v.bestWeek} reduce={reduce}/></div>;
  case 'peak_week':return <Center label="YOUR HIGHEST WEEK" value={num(v.score)} title={'Week '+v.week+'. Your moment.'}><p>{v.wasWeeklyLeader?'YOU MATCHED THE WEEKLY HIGH':'YOUR PERSONAL SEASON HIGH · POINTS'}</p></Center>;
  case 'game_compare':return <div className="saga-wide"><h1>{beat.headline}</h1><Compare games={v.games}/><p className="saga-caveat">AVERAGE POINTS PER COMPLETED GAME · CREW = OTHER PLAYERS, EQUALLY WEIGHTED</p></div>;
  case 'game_dna':return <div className="saga-wide"><h1>Your CREW DNA.</h1><GameDna games={v.games} totalPoints={v.totalPoints}/></div>;
  case 'plot_twist':return <Center label="THE PLOT TWIST" value={beat.metric} title={beat.headline}><p>{beat.description}</p></Center>;
  case 'trophy_vault':return <div className="saga-vault"><Center label="THE TROPHY VAULT" value={num(v.badges.length)} title="Badges unlocked."/><div className="saga-vault-grid">{v.badges.map((b,i)=><m.div key={b.code} initial={{opacity:0,scale:.7}} animate={{opacity:1,scale:1}} transition={{duration:.7,delay:.12*i}}><Badge item={b} size="small"/>{v.celebrated?.includes(b.code)&&<small className="saga-already-celebrated">TITLE CELEBRATED</small>}</m.div>)}</div></div>;
  case 'legacy':return <Legacy v={v} recap={recap}/>;
  case 'season_two':return <Center label="THE STORY CONTINUES" value="02" title="SEASON 02"><p>New games. New rivalries. A new champion.</p><small>YOUR NEXT CHAPTER AWAITS</small></Center>;
  default:return null;
 }
}

import React, {useEffect, useState} from 'react';
import {AnimatePresence, m} from 'motion/react';
import {BadgeMedallion} from './TrophyRoom';
import ChampionReveal from './ChampionReveal';

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
// One changing spotlight, never four comparison cards at once. Scene duration
// is coordinated with the cinema's autoplay timer (3.8 s per played game).
function Compare({games, reduce, playing}){
 const shown=games.filter(g=>g.mine!==null);
 const [step,setStep]=useState(0);
 useEffect(()=>{
   if(!playing||reduce||shown.length<2)return undefined;
   const timer=window.setInterval(()=>setStep(current=>Math.min(current+1,shown.length-1)),3800);
   return ()=>window.clearInterval(timer);
 },[playing,reduce,shown.length]);
 const game=shown[Math.min(step,shown.length-1)];
 if(!game)return null;
 const delta=game.crew===null?null:Math.round((game.mine-game.crew)*10)/10;
 const message=delta===null?'NO PEER BENCHMARK AVAILABLE':
   delta>0?'ABOVE THE CREW AVERAGE':delta<0?'BELOW THE CREW AVERAGE':'RIGHT ON THE CREW AVERAGE';
 return <div className="saga-spotlight" style={{'--game':KEYS[game.key]}}>
   <div className="saga-spotlight-picks" role="group" aria-label="Choose game comparison">
    {shown.map((g,i)=><button key={g.key} type="button" className={'saga-spotlight-pick'+(step===i?' is-active':'')}
       style={{'--pick':KEYS[g.key]}} onClick={()=>setStep(i)} aria-pressed={step===i}
       aria-label={'Show '+g.name+' comparison'}>{g.name.split(' ')[0]}</button>)}
   </div>
   <AnimatePresence mode="wait" initial={false}>
    <m.div key={game.key} className="saga-spotlight-stage" initial={reduce?false:{opacity:0,y:18,filter:'blur(8px)'}}
      animate={{opacity:1,y:0,filter:'blur(0px)'}} exit={reduce?{opacity:0}:{opacity:0,y:-16,filter:'blur(8px)'}}
      transition={{duration:reduce?0:.48,ease:[.22,1,.36,1]}}>
      <span className="saga-kicker">GAME {String(step+1).padStart(2,'0')} / {String(shown.length).padStart(2,'0')}</span>
      <h2>{game.name}</h2>
      <div className="saga-spotlight-scores">
       {[
          {label:'YOU',value:game.mine,lead:true},
          {label:'CREW AVERAGE',value:game.crew,lead:false}
       ].map(item=><div key={item.label} className={'saga-spotlight-score'+(item.lead?' is-you':'')}>
         <div className="saga-spotlight-score-head"><span>{item.label}</span><strong>{item.value===null?'—':num(item.value)}</strong></div>
         <div className="saga-spotlight-rail"><m.i initial={reduce?false:{scaleX:0}}
            animate={{scaleX:item.value===null?0:Math.max(0,Math.min(1,item.value/100))}}
            transition={{duration:reduce?0:1.25,delay:reduce?0:.18,ease:[.22,1,.36,1]}}/></div>
        </div>)}
      </div>
      <div className="saga-spotlight-result" aria-live="polite">
        {delta!==null&&<strong>{delta>0?'+':delta<0?'−':''}{num(Math.abs(delta))} <small>PTS</small></strong>}
        <span>{message}</span>
      </div>
    </m.div>
   </AnimatePresence>
 </div>;
}
function GameDna({games,totalPoints,reduce}){
 if(totalPoints<=0)return null;
 const strongest=games.reduce((a,b)=>b.points>a.points?b:a,games[0]);
 const tied=games.filter(g=>g.points===strongest.points).length>1;
 return <div className="saga-dna-focus">
   <span className="saga-kicker">YOUR POINTS · FOUR GAMES</span>
   <div className="saga-dna-focus-bar" role="img"
     aria-label={games.map(g=>g.name+': '+g.pointShare.toFixed(1)+'% of your points').join('; ')}>
     {games.map((g,i)=><m.div key={g.key} className="saga-dna-focus-segment"
       style={{background:KEYS[g.key]}} title={g.name+': '+g.pointShare.toFixed(1)+'%'}
       initial={reduce?false:{flexGrow:0,opacity:.35}}
       animate={{flexGrow:g.pointShare,opacity:1}}
       transition={{duration:reduce?0:1.65,delay:reduce?0:.12*i,ease:[.22,1,.36,1]}}/>)}
   </div>
   <div className="saga-dna-focus-legend">
     {games.map(g=><div key={g.key} style={{'--game':KEYS[g.key]}}>
       <i aria-hidden="true"/><span>{g.name}</span><strong>{g.pointShare.toFixed(1)}%</strong>
     </div>)}
   </div>
   <m.p className="saga-dna-focus-insight" initial={reduce?false:{opacity:0,y:10}}
     animate={{opacity:1,y:0}} transition={{duration:reduce?0:.8,delay:reduce?0:1.7}}>
     <strong>{strongest.name}</strong> {tied?'was one of your top point contributors.':'powered the largest share of your season.'}
     <span> {strongest.pointShare.toFixed(1)}% of your total points.</span>
   </m.p>
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
export default function RewindSagaScene({beat,recap,reduce,playing}){
 const v=beat.visual||{};
 switch(beat.kind){
  case 'winner':
  case 'winner_badge':return <ChampionReveal beat={beat} recap={recap} reduce={reduce} playing={playing}/>;
  case 'welcome':return <Center label="CREW · SEASON 01" value="01" title={beat.headline}><p>{recap.username}, this story belongs to you.</p></Center>;
  case 'podium':return <Center label="THE PODIUM" value={v.count} title="Times among the weekly Top 3."><div className="saga-podium-weeks">{Array.from({length:v.weeksTotal},(_,i)=>{const w=v.weeks.find(x=>x.week===i+1);return <div key={i}><m.span className={'saga-podium-slot '+(w?'is-earned':'')} initial={{opacity:0,y:15}} animate={{opacity:1,y:0}} transition={{delay:i*.15}}>{w?'#'+w.place:'·'}</m.span><small>W{i+1}</small></div>})}</div><p>#{v.frequencyRank} for weekly podium appearances this season.</p></Center>;
  case 'weekly_trend':return <div className="saga-wide"><h1>{beat.headline}</h1><WeekLines weeks={v.weeks} bestWeek={v.bestWeek} reduce={reduce}/></div>;
  case 'peak_week':return <Center label="YOUR HIGHEST WEEK" value={num(v.score)} title={'Week '+v.week+'. Your moment.'}><p>{v.wasWeeklyLeader?'YOU MATCHED THE WEEKLY HIGH':'YOUR PERSONAL SEASON HIGH · POINTS'}</p></Center>;
  case 'game_compare':return <div className="saga-wide saga-game-compare"><h1>Your game. Your edge.</h1><Compare games={v.games} reduce={reduce} playing={playing}/><p className="saga-caveat">AVERAGE POINTS PER COMPLETED GAME · CREW = OTHER PLAYERS</p></div>;
  case 'game_dna':return <div className="saga-wide saga-game-dna"><h1>What powered your season.</h1><GameDna games={v.games} totalPoints={v.totalPoints} reduce={reduce}/></div>;
  case 'plot_twist':return <Center label="THE PLOT TWIST" value={beat.metric} title={beat.headline}><p>{beat.description}</p></Center>;
  case 'trophy_vault':return <div className="saga-vault"><Center label="THE TROPHY VAULT" value={num(v.badges.length)} title="Badges unlocked."/><div className="saga-vault-grid">{v.badges.map((b,i)=><m.div key={b.code} initial={{opacity:0,scale:.7}} animate={{opacity:1,scale:1}} transition={{duration:.7,delay:.12*i}}><Badge item={b} size="small"/>{v.celebrated?.includes(b.code)&&<small className="saga-already-celebrated">TITLE CELEBRATED</small>}</m.div>)}</div></div>;
  case 'legacy':return <Legacy v={v} recap={recap}/>;
  case 'season_two':return <Center label="THE STORY CONTINUES" value="02" title="SEASON 02"><p>New games. New rivalries. A new champion.</p><small>YOUR NEXT CHAPTER AWAITS</small></Center>;
  default:return null;
 }
}

import React, {useRef, useState} from 'react';
import {m, useMotionValueEvent, useTransform} from 'motion/react';
import {BadgeMedallion} from './TrophyRoom';
import ChampionReveal from './ChampionReveal';
import {SeasonPodium, SeasonGameMaster} from './SeasonHonors';
import {Reveal} from './RewindMotion';
import {COMPARE_STEP_MS, comparisonIndex, comparisonSeek} from './rewindTimeline';

const KEYS={mystery:'var(--crew-game-mystery,#55e6ac)',trivia:'var(--crew-game-trivia,#ffbd45)',word:'var(--crew-game-word,#55b9ff)',tick_tock:'var(--crew-game-tick-tock,#c55cff)'};
const num=n=>Number(n||0).toLocaleString('en-US',{maximumFractionDigits:1});

function Badge({item,size='large'}){
  return <div className={'saga-badge saga-badge-'+size}>
    <BadgeMedallion badge={item} size={size==='large'?'normal':'compact'} seasonNumber={1}/>
    <strong>{item.name}</strong><small>{item.rarity?.toUpperCase()}</small>
  </div>;
}
function Center({label,title,value,children,time}){
  return <div className="saga-center"><span className="saga-kicker">{label}</span>
    {value!==undefined&&<Reveal as="strong" time={time} scale={.85} className="saga-huge">{value}</Reveal>}
    <h1>{title}</h1>{children}</div>;
}
function WeekLines({weeks,bestWeek,time}){
  const highestPath=useTransform(time,[250,2450],[0,1]);
  const minePath=useTransform(time,[550,3150],[0,1]);
  const max=Math.max(1,...weeks.map(w=>w.highest));
  const at=(w,i,key)=>[(i/(Math.max(1,weeks.length-1)))*780+30,250-(w[key]/max)*195];
  const points=key=>weeks.map((w,i)=>at(w,i,key).join(',')).join(' ');
  return <div className="saga-chart" role="img" aria-label="Animated weekly player score compared with highest CREW player score">
    <svg viewBox="0 0 840 315" preserveAspectRatio="xMidYMid meet">
      {[0,.25,.5,.75,1].map(v=><line key={v} x1="30" x2="810" y1={250-195*v} y2={250-195*v} stroke="#617080" strokeOpacity=".21"/>)}
      <m.polyline points={points('highest')} fill="none" stroke="var(--crew-game-trivia,#ffbd45)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" style={{pathLength:highestPath}}/>
      <m.polyline points={points('mine')} fill="none" stroke="var(--crew-game-word,#55b9ff)" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" style={{pathLength:minePath}}/>
      {weeks.map((w,i)=><g key={w.week}>
        <circle cx={at(w,i,'mine')[0]} cy={at(w,i,'mine')[1]} r={w.week===bestWeek?9:5} fill="var(--crew-game-word,#55b9ff)"/>
        <text x={at(w,i,'mine')[0]} y="288" textAnchor="middle" fill="#adc3d7" fontSize="17">W{w.week}</text>
      </g>)}
    </svg>
    <div className="saga-chart-legend"><span><i style={{background:KEYS.word}}/>YOUR SCORE</span><span><i style={{background:KEYS.trivia}}/>WEEKLY HIGHEST</span></div>
  </div>;
}
// The spotlight and the chapter deadline read the same elapsed MotionValue.
function Compare({games, reduce, playing, time, seek}){
 const shown=games.filter(g=>g.mine!==null);
 const [step,setStep]=useState(()=>comparisonIndex(time.get(),shown.length));
 const activeStep=useRef(step);
 useMotionValueEvent(time,'change',value=>{
   const next=comparisonIndex(value,shown.length);
   if(activeStep.current!==next){activeStep.current=next;setStep(next);}
 });
 const game=shown[Math.min(step,shown.length-1)];
 if(!game)return null;
 const delta=game.crew===null?null:Math.round((game.mine-game.crew)*10)/10;
 const message=delta===null?'NO PEER BENCHMARK AVAILABLE':
   delta>0?'ABOVE THE CREW AVERAGE':delta<0?'BELOW THE CREW AVERAGE':'RIGHT ON THE CREW AVERAGE';
 return <div className="saga-spotlight" style={{'--game':KEYS[game.key]}}>
   <div className="saga-spotlight-picks" role="group" aria-label="Choose game comparison">
    {shown.map((g,i)=><button key={g.key} type="button" className={'saga-spotlight-pick'+(step===i?' is-active':'')}
       style={{'--pick':KEYS[g.key]}} onClick={()=>{seek(comparisonSeek(i,reduce||!playing));setStep(i);}} aria-pressed={step===i}
       aria-label={'Show '+g.name+' comparison'}>{g.name.split(' ')[0]}</button>)}
   </div>
   <Reveal time={time} start={step*COMPARE_STEP_MS} duration={350} className="saga-spotlight-stage" key={game.key}>
      <span className="saga-kicker">GAME {String(step+1).padStart(2,'0')} / {String(shown.length).padStart(2,'0')}</span>
      <h2>{game.name}</h2>
      <div className="saga-spotlight-scores">
       {[
          {label:'YOU',value:game.mine,lead:true},
          {label:'CREW AVERAGE',value:game.crew,lead:false}
       ].map(item=><div key={item.label} className={'saga-spotlight-score'+(item.lead?' is-you':'')}>
         <div className="saga-spotlight-score-head"><span>{item.label}</span><strong>{item.value===null?'—':num(item.value)}</strong></div>
         <div className="saga-spotlight-rail"><ScoreBar time={time} start={step*COMPARE_STEP_MS+180} value={item.value}/></div>
        </div>)}
      </div>
      <div className="saga-spotlight-result" aria-live="polite">
        {delta!==null&&<strong>{delta>0?'+':delta<0?'−':''}{num(Math.abs(delta))} <small>PTS</small></strong>}
        <span>{message}</span>
      </div>
    </Reveal>
 </div>;
}
function ScoreBar({time,start,value}){
 const scaleX=useTransform(time,[start,start+1250],[0,value===null?0:Math.max(0,Math.min(1,value/100))]);
 return <m.i style={{scaleX}}/>;
}
function DnaSegment({game,time,index}){
 const scaleY=useTransform(time,[200+index*120,1500+index*120],[0,1]);
 return <m.div className="saga-dna-focus-segment" style={{background:KEYS[game.key],flexGrow:game.pointShare,scaleY,transformOrigin:'bottom'}} title={game.name+': '+game.pointShare.toFixed(1)+'%'}/>;
}
function GameDna({games,totalPoints,time}){
 if(totalPoints<=0)return null;
 const strongest=games.reduce((a,b)=>b.points>a.points?b:a,games[0]);
 const tied=games.filter(g=>g.points===strongest.points).length>1;
 return <div className="saga-dna-focus">
   <span className="saga-kicker">YOUR POINTS · FOUR GAMES</span>
   <div className="saga-dna-focus-bar" role="img"
     aria-label={games.map(g=>g.name+': '+g.pointShare.toFixed(1)+'% of your points').join('; ')}>
     {games.map((g,i)=><DnaSegment key={g.key} game={g} index={i} time={time}/>)}
   </div>
   <div className="saga-dna-focus-legend">
     {games.map(g=><div key={g.key} style={{'--game':KEYS[g.key]}}>
       <i aria-hidden="true"/><span>{g.name}</span><strong>{g.pointShare.toFixed(1)}%</strong>
     </div>)}
   </div>
   <Reveal as="p" time={time} start={1700} className="saga-dna-focus-insight">
     <strong>{strongest.name}</strong> {tied?'was one of your top point contributors.':'powered the largest share of your season.'}
     <span> {strongest.pointShare.toFixed(1)}% of your total points.</span>
   </Reveal>
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
export default function RewindSagaScene({beat,recap,reduce,playing,time,seek}){
 const v=beat.visual||{};
 switch(beat.kind){
  case 'winner':
  case 'winner_badge':return <ChampionReveal beat={beat} recap={recap} reduce={reduce} playing={playing} time={time}/>;
  case 'season_podium':return <SeasonPodium visual={v} time={time} reduce={reduce}/>;
  case 'season_game_master':return <SeasonGameMaster visual={v} time={time} reduce={reduce}/>;
  case 'welcome':return <Center time={time} label="CREW · SEASON 01" value="01" title={beat.headline}><p>{recap.username}, this story belongs to you.</p></Center>;
  case 'podium':return <Center time={time} label="THE PODIUM" value={v.count} title="Times among the weekly Top 3."><div className="saga-podium-weeks">{Array.from({length:v.weeksTotal},(_,i)=>{const w=v.weeks.find(x=>x.week===i+1);return <div key={i}><Reveal as="span" time={time} start={200+i*150} className={'saga-podium-slot '+(w?'is-earned':'')}>{w?'#'+w.place:'·'}</Reveal><small>W{i+1}</small></div>})}</div><p>#{v.frequencyRank} for weekly podium appearances this season.</p></Center>;
  case 'weekly_trend':return <div className="saga-wide"><h1>{beat.headline}</h1><WeekLines weeks={v.weeks} bestWeek={v.bestWeek} time={time}/></div>;
  case 'peak_week':return <Center time={time} label="YOUR HIGHEST WEEK" value={num(v.score)} title={'Week '+v.week+'. Your moment.'}><p>{v.wasWeeklyLeader?'YOU MATCHED THE WEEKLY HIGH':'YOUR PERSONAL SEASON HIGH · POINTS'}</p></Center>;
  case 'game_compare':return <div className="saga-wide saga-game-compare"><h1>Your game. Your edge.</h1><Compare games={v.games} reduce={reduce} playing={playing} time={time} seek={seek}/><p className="saga-caveat">AVERAGE POINTS PER COMPLETED GAME · CREW = OTHER PLAYER ACCOUNTS</p></div>;
  case 'game_dna':return <div className="saga-wide saga-game-dna"><h1>What powered your season.</h1><GameDna games={v.games} totalPoints={v.totalPoints} time={time}/></div>;
  case 'plot_twist':return <Center time={time} label="THE PLOT TWIST" value={beat.metric} title={beat.headline}><p>{beat.description}</p></Center>;
  case 'trophy_vault':return <div className="saga-vault"><Center time={time} label="THE TROPHY VAULT" value={num(v.badges.length)} title="Badges unlocked."/><div className="saga-vault-grid">{v.badges.map((b,i)=><Reveal key={b.code} time={time} scale={.85} start={200+120*i}><Badge item={b} size="small"/>{v.celebrated?.includes(b.code)&&<small className="saga-already-celebrated">TITLE CELEBRATED</small>}</Reveal>)}</div></div>;
  case 'legacy':return <Legacy v={v} recap={recap}/>;
  case 'season_two':return <Center time={time} label="THE STORY CONTINUES" value="02" title="SEASON 02"><p>New games. New rivalries. A new champion.</p><small>YOUR NEXT CHAPTER AWAITS</small></Center>;
  default:return null;
 }
}


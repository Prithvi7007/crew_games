import React from 'react';
import {m, useTransform} from 'motion/react';

// Every flourish reads the chapter clock: pause, seek and replay have one owner.
function ConfettiPiece({time,index,start}) {
  const side=index%2===0?1:-1;
  const delay=(index%9)*65;
  const progress=useTransform(time,[start+delay,start+delay+4400],[0,1]);
  const opacity=useTransform(progress,[0,.035,.7,1],[0,1,.9,0]);
  const x=useTransform(progress,p=>side*(12+(index*7%23))*(1-(1-p)**2)+'vw');
  const y=useTransform(progress,p=>(-4*(22+index*5%15)*p*(1-p)+18*p*p)+'vh');
  const rotate=useTransform(progress,[0,1],[index*29,index*29+side*(420+index*17)]);
  const scaleX=useTransform(progress,p=>.3+.7*Math.abs(Math.cos(p*6*Math.PI+index)));
  return <m.i className="champion-confetti" data-side={side===1?'left':'right'}
    style={{opacity,x,y,rotate,scaleX,'--confetti-color':[
      'var(--champion-accent)','#ffe5a3','#f5f8ff','var(--champion-accent)',
    ][index%4]}}/>;
}

export default function ChampionCelebration({time,closeup,reduce}) {
  const start=closeup?350:1900;
  const opacity=useTransform(time,[start,start+1000,start+2600,start+5200],[0,.8,.55,.28]);
  const scale=useTransform(time,[start,start+1300,start+5200],[.65,1.12,1]);
  const rotate=useTransform(time,[start,start+5200],[-12,12]);
  return <div className="champion-celebration" aria-hidden="true">
    <div className="champion-halo-position">
      <m.div className="champion-halo" style={reduce?{opacity:.35}:{opacity,scale,rotate}}/>
    </div>
    {!reduce&&Array.from({length:closeup?18:36},(_,index)=>
      <ConfettiPiece key={index} time={time} index={index} start={closeup?1100:2850}/>)}
  </div>;
}

export function ChampionBadgeMotion({time,closeup,reduce,children}) {
  const start=closeup?350:1600;
  const scale=useTransform(time,[start,start+700,start+1100,start+1500],[.76,1.08,.985,1]);
  const rotate=useTransform(time,[start,start+700,start+1100,start+1500],[-7,2,-.5,0]);
  const shineStart=closeup?1900:3450;
  const x=useTransform(time,[shineStart,shineStart+1300],['0%','520%']);
  const opacity=useTransform(time,[shineStart,shineStart+200,shineStart+1050,shineStart+1300],[0,.55,.4,0]);
  return <m.div className="champion-badge-lift" style={reduce?undefined:{scale,rotate}}>
    {children}
    {!reduce&&<span className="champion-badge-polish" aria-hidden="true">
      <m.i className="champion-badge-shine" style={{x,opacity,rotate:20}}/>
    </span>}
  </m.div>;
}

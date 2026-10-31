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
  return <div className="champion-celebration" aria-hidden="true">
    {!reduce&&Array.from({length:closeup?18:36},(_,index)=>
      <ConfettiPiece key={index} time={time} index={index} start={closeup?1100:3150}/>)}
  </div>;
}

export function ChampionBadgeMotion({time,closeup,reduce,children}) {
  const start=closeup?350:2600;
  const impact=closeup?1100:3150;
  const scale=useTransform(time,[start,start+750,start+1150,start+1500],[.45,1.12,.985,1]);
  const rotate=useTransform(time,[start,start+750,start+1150,start+1500],[-9,2,-.5,0]);
  const halo=useTransform(time,[start,start+750,start+2000,start+4000],[0,.8,.45,.25]);
  const ringScale=useTransform(time,[impact,impact+1800],[.8,1.85]);
  const ringOpacity=useTransform(time,[impact,impact+150,impact+1450,impact+1800],[0,.7,.2,0]);
  const shineStart=closeup?1900:4300;
  const x=useTransform(time,[shineStart,shineStart+1300],['0%','520%']);
  const opacity=useTransform(time,[shineStart,shineStart+200,shineStart+1050,shineStart+1300],[0,.55,.4,0]);
  return <m.div className="champion-badge-lift" style={reduce?undefined:{scale,rotate}}>
    <m.div className="champion-halo" aria-hidden="true" style={{opacity:reduce ? .35 : halo}}/>
    {!reduce&&<m.i className="champion-impact-ring" aria-hidden="true" style={{scale:ringScale,opacity:ringOpacity}}/>}
    {children}
    {!reduce&&<span className="champion-badge-polish" aria-hidden="true">
      <m.i className="champion-badge-shine" style={{x,opacity,rotate:20}}/>
    </span>}
  </m.div>;
}

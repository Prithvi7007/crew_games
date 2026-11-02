import React from 'react';
import {cubicBezier} from 'motion';
import {m, useTransform} from 'motion/react';

const settle=cubicBezier(.22,1,.36,1);

function Clue({index,time,cue}){
  const angle=(index*120-90)*Math.PI/180;
  const x=Math.cos(angle)*100,y=Math.sin(angle)*100;
  const start=200+index*230;
  const pathLength=useTransform(time,[start,start+700],[0,1]);
  const scale=useTransform(time,[start,start+500,cue.badge,cue.impact],[.4,1,1,.12],{ease:settle});
  const opacity=useTransform(time,[start,start+200,cue.badge,cue.impact],[0,1,1,0]);
  return <g>
    <m.path d={'M '+(160+x)+' '+(160+y)+' L 160 160'} style={{pathLength,opacity}}/>
    <m.g style={{x:160+x,y:160+y,scale,opacity}}>
      <circle r="18"/><path d="M -6 0 L 0 -6 L 6 0 L 0 6 Z"/>
    </m.g>
  </g>;
}

function Choice({index,time,cue}){
  const start=150+index*160;
  const x=useTransform(time,[start,start+500,cue.badge,cue.impact],[0,[-92,92,-92,92][index],[-92,92,-92,92][index],0],{ease:settle});
  const y=useTransform(time,[start,start+500,cue.badge,cue.impact],[0,[-62,-62,62,62][index],[-62,-62,62,62][index],0],{ease:settle});
  const opacity=useTransform(time,[start,start+200,cue.badge,cue.impact],[0,.9,.9,0]);
  const rotate=useTransform(time,[start,cue.impact],[-12,0],{ease:settle});
  return <m.g style={{x,y,opacity,rotate}}>
    <rect x="134" y="142" width="52" height="36" rx="8"/>
    <path d="M 151 160 L 158 167 L 171 153"/>
  </m.g>;
}

function CrewTile({letter,index,time,cue}){
  const start=250+index*190;
  const rotateX=useTransform(time,[start,start+600],[85,0],{ease:settle});
  const x=useTransform(time,[cue.badge-300,cue.impact],[(index-1.5)*115+'%','0%'],{ease:settle});
  const opacity=useTransform(time,[start,start+150,cue.badge-250,cue.impact],[0,1,1,0]);
  const scale=useTransform(time,[cue.badge-300,cue.impact],[1,.25],{ease:settle});
  return <m.span className="master-crew-tile" style={{rotateX,x,opacity,scale}}>{letter}</m.span>;
}

function Dial({time,cue}){
  const pathLength=useTransform(time,[200,cue.badge],[0,1],{ease:settle});
  const rotate=useTransform(time,[200,cue.badge,cue.impact],[-125,0,0],{ease:settle});
  const opacity=useTransform(time,[100,350,cue.impact,cue.impact+450],[0,.9,.9,0]);
  return <m.g style={{opacity}}>
    {Array.from({length:12},(_,i)=><path key={i} d="M 160 40 L 160 52" transform={'rotate('+i*30+' 160 160)'}/>)}
    <m.circle cx="160" cy="160" r="98" style={{pathLength}}/>
    <m.g style={{rotate,transformOrigin:'160px 160px'}}><path d="M 160 160 L 160 83"/><circle cx="160" cy="160" r="8"/></m.g>
  </m.g>;
}

// Branded geometry only: these aren't historical clues, answers or timer results.
// No autonomous animation: every flourish freezes with the chapter MotionValue.
export default function MasterSignature({game,time,cue,reduce}){
  if(reduce)return null;
  return <div className={'master-signature master-signature-'+game} aria-hidden="true">
    {game==='word'?<div className="master-crew-tiles">
      {'CREW'.split('').map((letter,index)=><CrewTile key={index} letter={letter} index={index} time={time} cue={cue}/>)}</div>:
    <svg viewBox="0 0 320 320" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      {game==='mystery'?Array.from({length:3},(_,index)=><Clue key={index} index={index} time={time} cue={cue}/>):
       game==='tick_tock'?<Dial time={time} cue={cue}/>:Array.from({length:4},(_,index)=><Choice key={index} index={index} time={time} cue={cue}/>) }
    </svg>}
  </div>;
}

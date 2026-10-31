import React from 'react';
import {cubicBezier} from 'motion';
import {m, useTransform} from 'motion/react';

const revealEase=cubicBezier(.16,1,.3,1);

// The mask provides the reveal; complete text stays intact for names and readers.
export function ChampionLine({as='h1',time,start,duration=1100,reduce,className,children}) {
  const y=useTransform(time,[start,start+duration],['110%','0%'],{ease:revealEase});
  const opacity=useTransform(time,[start,start+220],[0,1]);
  const Element=m[as];
  return <Element className={className+' champion-line'} style={{opacity:reduce?1:opacity}}>
    <m.span className="champion-line-inner" style={reduce?undefined:{y}}>{children}</m.span>
  </Element>;
}

export default function ChampionStageLights({time,reduce}) {
  const opacity=useTransform(time,[0,450,1500,3150,4800],[0,.5,.8,.55,.12]);
  const left=useTransform(time,[0,1500,3150,4800],[-32,18,18,8],{ease:revealEase});
  const right=useTransform(time,[0,1500,3150,4800],[32,-18,-18,-8],{ease:revealEase});
  const floor=useTransform(time,[500,1800,3150,5000],[0,.45,.8,.25]);
  const scaleX=useTransform(time,[500,3150],[.2,1],{ease:revealEase});
  if(reduce)return null;
  return <div className="champion-stage-lights" aria-hidden="true">
    <m.i className="champion-beam champion-beam-left" style={{opacity,rotate:left}}/>
    <m.i className="champion-beam champion-beam-right" style={{opacity,rotate:right}}/>
    <m.i className="champion-floor-light" style={{opacity:floor,scaleX}}/>
  </div>;
}

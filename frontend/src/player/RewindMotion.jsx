import React, {useCallback, useEffect, useRef, useState} from 'react';
import {cubicBezier} from 'motion';
import {animate, m, useIsPresent, useMotionValue, useTransform} from 'motion/react';
import {chapterDuration, comparisonIndex, comparisonSeek, initialChapterTime, resumeChapterTime, runChapterClock} from './rewindTimeline';

const chapterVariants={
  enter:direction=>({opacity:0,y:direction*12,scale:.992}),
  center:{opacity:1,y:0,scale:1},
  exit:direction=>({opacity:0,y:-direction*6,transition:{duration:.24}}),
};
const revealEase=cubicBezier(.22,1,.36,1);

export function Reveal({time,as='div',start=200,duration=700,scale=1,className,children,...props}) {
  const opacity=useTransform(time,[start,start+duration],[0,1]);
  const y=useTransform(time,[start,start+duration],[18,0],{ease:revealEase});
  const size=useTransform(time,[start,start+duration],[scale,1],{ease:revealEase});
  const Element=m[as];
  return <Element {...props} className={className} style={{opacity,y,scale:size}}>{children}</Element>;
}

export default function RewindChapter({beat,playing,reduce,finished,direction,onFinish,children}) {
  const present=useIsPresent();
  const duration=chapterDuration(beat);
  const time=useMotionValue(initialChapterTime(beat,playing&&!reduce));
  const [visible,setVisible]=useState(()=>document.visibilityState!=='hidden');
  const [revision,setRevision]=useState(0);
  const stop=useRef(null);
  const still=useRef(!playing||reduce);
  useEffect(()=>{
    const change=()=>{if(document.hidden)stop.current?.();setVisible(!document.hidden);};
    document.addEventListener('visibilitychange',change);
    return ()=>document.removeEventListener('visibilitychange',change);
  },[]);
  useEffect(()=>{
    if(finished){time.set(duration);return undefined;}
    if(reduce){
      still.current=true;
      const count=(beat.visual?.games||[]).filter(g=>g.mine!==null).length;
      time.set(beat.kind==='game_compare'?comparisonSeek(comparisonIndex(time.get(),count),true):duration);
    }
    if(!playing||reduce||!visible||!present)return undefined;
    time.set(resumeChapterTime(beat,time.get(),still.current));
    still.current=false;
    const cleanup=runChapterClock({elapsed:time,duration,animate,
      schedule:(fn,ms)=>window.setTimeout(fn,ms),cancel:id=>window.clearTimeout(id),onFinish});
    stop.current=cleanup;
    return ()=>{cleanup();stop.current=null;};
  },[playing,reduce,finished,visible,present,duration,time,onFinish,revision,beat]);
  const seek=useCallback(value=>{
    stop.current?.();time.set(Math.max(0,Math.min(duration,value)));setRevision(v=>v+1);
  },[time,duration]);
  return <m.section className="rc-frame" aria-live="polite"
    custom={direction} variants={chapterVariants}
    initial={reduce||!playing?false:'enter'} animate="center"
    exit={reduce?{opacity:0}:'exit'}
    transition={{duration:reduce?0:.48,ease:[.22,1,.36,1]}}>
    {children({time,seek})}
  </m.section>;
}


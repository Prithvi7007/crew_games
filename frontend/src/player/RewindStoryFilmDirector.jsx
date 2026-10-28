import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {AnimatePresence, LazyMotion, MotionConfig, domAnimation, m, useReducedMotion} from 'motion/react';
import RewindDirectorScenes from './RewindDirectorScenes';

const PALETTE={
  opening:['#8bd6ff','#5d83b9'],rivalry:['#a5f5df','#d5a0ce'],
  trajectory:['#8adff5','#d2a0ee'],swing:['#b5f3d2','#ffcfa1'],
  pivot:['#ffdd92','#f5a4bd'],strength:['#71e4f6','#a9c5f7'],
  standout:['#d0b3ff','#8be9db'],momentum:['#ffbaca','#db9dff'],
  consistency:['#b5ebc6','#69bada'],ending:['#fff0c3','#afbbff'],
};
const clamp=(n,lo,hi)=>Math.max(lo,Math.min(hi,n));
const durationFor=beat=>clamp(6100+Math.round((beat?.description?.length||0)*10),6800,9000);
// Narration complements the scene rather than reading chart labels aloud.
const short=(beat)=>{
  const v=beat.visual||{};
  if(beat.kind==='trajectory' && v.rival)
    return 'Two cumulative scores, six scheduled weeks. The marked week changed the gap more than any other.';
  if(beat.kind==='strength' && v.game)
    return 'Among games with enough peer data, '+v.game+' was where you gained the clearest edge.';
  if(beat.kind==='swing' && v.net>0 && v.other<0)
    return 'The other games favored your rival. One game turned that deficit into a lead.';
  if(beat.kind==='rivalry' && v.rival)
    return 'The closest season points total belonged to '+v.rival.name+'. Look how little separated you.';
  if(beat.kind==='standout' && v.peerCount)
    return 'One shared puzzle. The same challenge for everyone. This was a performance that stood out.';
  if(beat.kind==='pivot')
    return 'Take this week away while leaving every other player unchanged. The standings look very different.';
  if(beat.kind==='consistency' && v.weeksTotal)
    return 'Week after week, you kept coming back. That rhythm became part of your season.';
  if(beat.kind==='momentum')
    return 'Same game types, two halves of the season. Your scoring pace changed.';
  if(beat.kind==='ending' && Number(v.total)>0)
    return 'Every game added to a season that could only be yours.';
  return beat.description;
};
function formatCount(n){return String(n).padStart(2,'0');}

export default function RewindStoryFilmDirector({data}) {
  const recap=data.rewind||{};
  const story=recap.cinematicStory||{beats:[],title:'Your story',player:recap.username};
  const beats=story.beats||[];
  const [index,setIndex]=useState(0);
  const [playing,setPlaying]=useState(false);
  const [details,setDetails]=useState(false);
  const reduce=useReducedMotion();
  const active=beats[index];
  const last=beats.length>0&&index===beats.length-1;
  const timerRef=useRef(null);
  const startRef=useRef(0);
  const remainingRef=useRef(null);
  const sceneRef=useRef(index);
  const back='/rewind?preview=1&prototype=1&analysis=1'+(data.rewindPreviewPlayer?'&player='+encodeURIComponent(data.rewindPreviewPlayer):'');
  const duration=durationFor(active);
  const colors=PALETTE[active?.kind]||PALETTE.opening;

  const jump=useCallback(target=>{
    setPlaying(false);
    setDetails(false);
    remainingRef.current=null;
    sceneRef.current=target;
    setIndex(target);
  },[]);
  const next=useCallback(()=>jump(Math.min(beats.length-1,index+1)),[jump,index,beats.length]);
  const previous=useCallback(()=>jump(Math.max(0,index-1)),[jump,index]);
  const replay=useCallback(()=>jump(0),[jump]);
  const toggle=useCallback(()=>{
    if(last){jump(0);setPlaying(!reduce);return;}
    if(reduce){next();return;}
    setDetails(false);
    setPlaying(p=>!p);
  },[last,jump,reduce,next]);

  useEffect(()=>{
    if(!playing||reduce||last||beats.length<2) return undefined;
    if(sceneRef.current!==index){sceneRef.current=index;remainingRef.current=null;}
    const left=remainingRef.current??duration;
    let completed=false;
    startRef.current=performance.now();
    timerRef.current=setTimeout(()=>{
      completed=true;
      remainingRef.current=null;
      setDetails(false);
      setIndex(i=>Math.min(beats.length-1,i+1));
    },left);
    return ()=>{
      clearTimeout(timerRef.current);
      if(!completed&&sceneRef.current===index){
        remainingRef.current=Math.max(250,left-(performance.now()-startRef.current));
      }
    };
  },[playing,reduce,index,last,beats.length,duration]);
  useEffect(()=>{if(last)setPlaying(false);},[last]);
  useEffect(()=>{
    const keyHandler=e=>{
      const target=e.target;
      if(target?.closest?.('input, textarea, select, button, a, [contenteditable=true]'))return;
      if(e.key==='ArrowRight'){e.preventDefault();next();}
      if(e.key==='ArrowLeft'){e.preventDefault();previous();}
      if(e.code==='Space'){e.preventDefault();toggle();}
    };
    window.addEventListener('keydown',keyHandler);
    return ()=>window.removeEventListener('keydown',keyHandler);
  },[next,previous,toggle]);

  const remaining=remainingRef.current??duration;
  const progressKey=index+'-'+(playing?'playing':'paused');
  const accentStyle={'--rd-primary':colors[0],'--rd-secondary':colors[1]};
  const isReady=Boolean(active);
  const sceneText=useMemo(()=>active?short(active):'', [active]);

  if(!isReady)return <main className="rd-empty"><p>There is no eligible Season 01 story yet.</p><a href={back}>Return to research</a></main>;

  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user">
    <main className={'rd-film rd-film-'+active.kind} style={accentStyle} aria-label={'CREW Rewind cinematic story for '+story.player}>
      <link rel="stylesheet" href="/static/css/rewind-director.css" />
      <div className="rd-ambient" aria-hidden="true">
        <m.div className="rd-aura-one" animate={{rotate:360,scale:[1,1.11,1]}} transition={{rotate:{duration:45,ease:'linear',repeat:Infinity},scale:{duration:12,repeat:Infinity}}}/>
        <m.div className="rd-aura-two" animate={{rotate:-360}} transition={{duration:65,ease:'linear',repeat:Infinity}}/>
        <div className="rd-skyline"/>
        <div className="rd-noise"/>
      </div>

      <header className="rd-masthead">
        <div className="rd-mark"><strong>CREW<span>✳</span></strong><small>SEASON 01 / REWIND</small></div>
        <span className="rd-viewer">{story.player} <i/> {recap.finalized?'FINALIZED':'PRIVATE PREVIEW'}</span>
        <a href={back} className="rd-exit" aria-label="Exit to research report"><span>EXIT FILM</span> ✕</a>
      </header>

      <div className="rd-chapters" aria-label="Navigate the story">
        {beats.map((b,i)=><button type="button" key={i} className={'rd-chapter'+(i===index?' is-current':'')+(i<index?' is-seen':'')}
            aria-current={i===index?'step':undefined} aria-label={'Chapter '+(i+1)+': '+b.eyebrow}
            onClick={()=>jump(i)}>
          <span className="rd-chapter-line"/>
          {i<index&&<span className="rd-chapter-done"/>}
          {i===index&&<m.span className="rd-chapter-running" key={progressKey}
            initial={{scaleX:playing&&!reduce?(duration-remaining)/duration:0}}
            animate={{scaleX:playing&&!reduce?1:0}}
            transition={{duration:playing&&!reduce?remaining/1000:0,ease:'linear'}}/>}
        </button>)}
      </div>

      <section className="rd-theater" aria-live="polite" aria-label="Your personalized season story">
        <AnimatePresence initial={false} mode="wait">
          <m.div key={'copy-'+index} className="rd-copy" initial={reduce?false:{opacity:0,y:38,filter:'blur(14px)'}}
            animate={{opacity:1,y:0,filter:'blur(0px)'}}
            exit={reduce?{opacity:0}:{opacity:0,y:-32,filter:'blur(14px)'}}
            transition={{duration:reduce?0:.88,ease:[.2,.8,.2,1]}}>
            <div className="rd-page-eyebrow"><span>CHAPTER {formatCount(index+1)}</span><i/>{active.eyebrow}</div>
            <h1>{active.headline}</h1>
            <p className="rd-declaration">{sceneText}</p>
            <div className="rd-detail-group">
              <button className="rd-evidence-toggle" type="button" aria-expanded={details}
                onClick={()=>{setPlaying(false);setDetails(v=>!v);}}>
                <span className="rd-evidence-icon">{details?'−':'+'}</span> {details?'Hide the evidence':'See how we know'}
              </button>
              <AnimatePresence>
                {details&&<m.div className="rd-evidence-panel" initial={{opacity:0,height:0}} animate={{opacity:1,height:'auto'}}
                  exit={{opacity:0,height:0}} transition={{duration:.3}}>
                  <p className="rd-evidence-label">THE EVIDENCE</p><p>{active.evidence}</p>
                  <p className="rd-evidence-note">Only cutoff-eligible completed games are included. This is an analytical comparison, not a claim about an unobserved play.</p>
                </m.div>}
              </AnimatePresence>
            </div>
          </m.div>
        </AnimatePresence>

        <div className="rd-visual-stage">
          <AnimatePresence initial={false} mode="wait">
            <m.div key={'visual-'+index} className={'rd-visual-shell rd-scene-'+active.kind}
              initial={reduce?false:{opacity:0,x:70,scale:.92,filter:'blur(21px)'}}
              animate={{opacity:1,x:0,scale:1,filter:'blur(0px)'}}
              exit={reduce?{opacity:0}:{opacity:0,x:-55,scale:1.04,filter:'blur(19px)'}}
              transition={{duration:reduce?0:1.15,ease:[.22,1,.36,1]}}>
              <RewindDirectorScenes beat={active} recap={recap}/>
            </m.div>
          </AnimatePresence>
        </div>
      </section>

      <footer className="rd-footbar">
        <div className="rd-playback">
          <button type="button" className="rd-step" disabled={index===0} onClick={previous} aria-label="Previous scene">←</button>
          <button type="button" className="rd-play-button" onClick={last?replay:toggle}>
            {last?'WATCH AGAIN':reduce?'NEXT CHAPTER':playing?'PAUSE FILM':index===0?'BEGIN MY REWIND':'CONTINUE FILM'}
            <span aria-hidden="true">{last?'↺':playing?'Ⅱ':'▶'}</span>
          </button>
          <button type="button" className="rd-step" disabled={last} onClick={next} aria-label="Next scene">→</button>
        </div>
      </footer>
    </main>
  </MotionConfig></LazyMotion>;
}

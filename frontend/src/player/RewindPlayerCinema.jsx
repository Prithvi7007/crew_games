import React, {useCallback, useEffect, useRef, useState} from 'react';
import {AnimatePresence, LazyMotion, MotionConfig, domAnimation, m, useReducedMotion} from 'motion/react';
import RewindDirectorScenes from './RewindDirectorScenes';
import RewindSagaScene from './RewindSagaScene';

const TONES={
  opening:['#a5dfff','#536dce'], rivalry:['#93f2e0','#b48aee'],
  trajectory:['#79deeb','#bf92de'], swing:['#a2f5d9','#e6b97f'],
  pivot:['#f5d18d','#dc8eb3'], strength:['#85e5f0','#a79cf0'],
  standout:['#c8a8f5','#85dbda'], momentum:['#f2a9c8','#998ef0'],
  consistency:['#a7edc2','#68bfcd'], ending:['#e9d6a4','#9faeea'],
};
const motionIn={opacity:0,y:22,filter:'blur(9px)'};
const motionOut={opacity:0,y:-18,filter:'blur(8px)'};
const smooth={duration:.85,ease:[.22,1,.36,1]};
const fmt=v=>String(v??'').replace(/\s+pts?$/i,'');
const secFor=beat=>beat?.kind==='game_compare'
  ? 1800+Math.max(1,(beat.visual?.games||[]).filter(g=>g.mine!==null).length)*3800
  :Math.min(11000,Math.max(7200,6800+(beat?.headline?.length||0)*30));
const noRepeat=(beat)=>{
  const v=beat.visual||{};
  switch(beat.kind){
    case 'opening': return 'Six weeks. A season of moments that were uniquely yours.';
    case 'rivalry': return v.rival ? 'A season-long contest, told by the final totals.' : beat.description;
    case 'trajectory': return 'See how the lead moved across the scheduled weeks.';
    case 'swing': return v.other<0 ? 'One game changed the balance of the entire season.' : beat.description;
    case 'pivot': return 'Remove one week. Keep everyone else exactly where they finished.';
    case 'strength': return 'Your strongest advantage against the wider field.';
    case 'standout': return 'One puzzle. A shared challenge. A moment that was yours.';
    case 'momentum': return 'The pace changed between the first and second half.';
    case 'consistency': return 'You kept showing up. Week after week.';
    case 'ending': return 'Every game. Every decision. Every surprise. This was your season.';
    default: return beat.description;
  }
};
const openerLabel=(beat)=>{
  const match=beat.description?.match(/separated you and ([^.]+)/i);
  if(beat.visual?.motif==='rivalry'&&match)
    return 'Every point mattered. Your closest rival: '+match[1]+'.';
  return beat.description;
};

function FilmMoment({beat,recap,player,reduce}){
  const kind=beat.kind;
  const opener=kind==='opening';
  const ending=kind==='ending';
  const graphic=!(opener||ending);
  const main=kind==='trajectory'?'rc-moment-trajectory':
    kind==='rivalry'?'rc-moment-rivalry':
    kind==='swing'?'rc-moment-swing':
    ['pivot','strength','standout','momentum','consistency'].includes(kind)?'rc-moment-insight':
    'rc-moment-hero';
  return <div className={'rc-moment '+main+' rc-kind-'+kind}>
    <div className="rc-scene-glow" aria-hidden="true"/>
    {opener||ending?
      <div className="rc-hero">
        <m.div className="rc-hero-kicker" initial={reduce?false:motionIn} animate={{opacity:1,y:0,filter:'blur(0px)'}} transition={{...smooth,delay:.15}}>
          CREW <span>✳</span> SEASON 01
        </m.div>
        <m.div className="rc-hero-figure" initial={reduce?false:{opacity:0,scale:.7,filter:'blur(35px)'}} animate={{opacity:1,scale:1,filter:'blur(0px)'}} transition={{duration:reduce?0:1.35,ease:[.16,1,.3,1]}}>
          {fmt(beat.metric)}
        </m.div>
        <m.h1 className="rc-hero-title" initial={reduce?false:motionIn} animate={{opacity:1,y:0,filter:'blur(0px)'}} transition={{...smooth,delay:.48}}>
          {ending?'That was your season.':beat.visual?.motif==='rivalry'?'POINTS APART.':beat.headline}
        </m.h1>
        <m.p className="rc-hero-description" initial={reduce?false:motionIn} animate={{opacity:1,y:0,filter:'blur(0px)'}} transition={{...smooth,delay:.76}}>
          {ending?player+' · '+noRepeat(beat):openerLabel(beat)}
        </m.p>
      </div>
    :<>
      <div className="rc-narration">
        <m.div className="rc-eyebrow" initial={reduce?false:motionIn} animate={{opacity:1,y:0,filter:'blur(0px)'}} transition={smooth}>YOUR SEASON <span>·</span> {beat.eyebrow}</m.div>
        <m.h2 initial={reduce?false:motionIn} animate={{opacity:1,y:0,filter:'blur(0px)'}} transition={{...smooth,delay:.16}}>{beat.headline}</m.h2>
        <m.p className="rc-deck" initial={reduce?false:motionIn} animate={{opacity:1,y:0,filter:'blur(0px)'}} transition={{...smooth,delay:.32}}>{noRepeat(beat)}</m.p>
      </div>
      <m.div className="rc-visual" initial={reduce?false:{opacity:0,scale:.88,filter:'blur(15px)'}}
        animate={{opacity:1,scale:1,filter:'blur(0px)'}} transition={{duration:reduce?0:1.1,delay:reduce?0:.28,ease:[.22,1,.36,1]}}>
        {graphic&&<RewindDirectorScenes beat={beat} recap={recap}/>}
      </m.div>
    </>}
  </div>;
}

export default function RewindPlayerCinema({data}){
  const recap=data.rewind||{};
  const saga=data.rewindSeasonSagaPreview===true;
  const story=(saga?recap.seasonSaga:recap.cinematicStory)||{beats:[],player:recap.username};
  const beats=story.beats||[];
  const [index,setIndex]=useState(0);
  const [playing,setPlaying]=useState(false);
  const [chrome,setChrome]=useState(false);
  const [evidence,setEvidence]=useState(false);
  const hideRef=useRef(null);
  const reduce=useReducedMotion();
  const scene=beats[index];
  const last=index===beats.length-1;
  const previewPlayer=data.rewindPreviewPlayer;
  const back='/rewind?preview=1&prototype=1&story='+(saga?'4':'3')+(previewPlayer?'&player='+encodeURIComponent(previewPlayer):'');
  const tone=TONES[scene?.kind]||TONES.opening;
  const go=useCallback(target=>{
    setIndex(i=>Math.max(0,Math.min(beats.length-1,target)));
    setEvidence(false);
    setChrome(false);
  },[beats.length]);
  const forward=useCallback(()=>go(index+1),[go,index]);
  const backward=useCallback(()=>go(index-1),[go,index]);
  const begin=useCallback(()=>{if(reduce){go(1);setChrome(true);}else{setPlaying(true);setChrome(false);}},[reduce,go]);
  const pause=useCallback(()=>{setPlaying(p=>!p);setChrome(true);},[]);
  const restart=useCallback(()=>{go(0);setPlaying(false);setChrome(false);},[go]);
  const reveal=useCallback(()=>{setChrome(true);},[]);

  // Motion timers are tied to the active chapter and are cancelled on every
  // transition, unmount, manual pause and evidence disclosure.
  useEffect(()=>{
    if(!playing||reduce||last||evidence||!scene)return undefined;
    const t=window.setTimeout(()=>setIndex(i=>Math.min(beats.length-1,i+1)),secFor(scene));
    return ()=>window.clearTimeout(t);
  },[playing,reduce,index,last,evidence,scene,beats.length]);
  useEffect(()=>{if(last)setPlaying(false);},[last]);
  useEffect(()=>{
    if(!chrome||!playing||evidence)return undefined;
    hideRef.current=window.setTimeout(()=>setChrome(false),3000);
    return ()=>window.clearTimeout(hideRef.current);
  },[chrome,playing,evidence,index]);
  useEffect(()=>{
    const handler=e=>{
      if(e.key==='Escape'){setEvidence(false);setChrome(false);return;}
      if(e.target?.closest?.('button,a,input,textarea,select,[contenteditable=true]'))return;
      if(e.key==='ArrowRight'){e.preventDefault();forward();}
      else if(e.key==='ArrowLeft'){e.preventDefault();backward();}
      else if(e.code==='Space'){e.preventDefault();if(index===0&&!playing)begin();else pause();}
    };
    window.addEventListener('keydown',handler);
    return ()=>window.removeEventListener('keydown',handler);
  },[forward,backward,begin,pause,index,playing]);
  if(!scene)return <main className="rc-empty"><h1>No season story yet.</h1><a href={back}>Back to Rewind</a></main>;
  const controls=chrome||(!playing&&index>0);
  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user">
    <main className={'rc-film rc-'+scene.kind+(playing?' rc-is-playing':'')+(saga?' saga-film':'')} style={{'--rc-light':tone[0],'--rc-glow':tone[1]}}
      aria-label={'Season 01 cinematic Rewind for '+story.player}
      onPointerMove={e=>{if(e.pointerType==='mouse')reveal();}}
      onPointerDown={e=>{if(e.pointerType==='touch'&&!e.target.closest('button,a'))setChrome(v=>!v);}}
      onFocusCapture={reveal}>
      <link rel="stylesheet" href="/static/css/rewind-director.css"/>
      <link rel="stylesheet" href="/static/css/rewind-cinema.css"/>
      {/* Saga CSS is loaded in the document head with a content fingerprint. */}
      <div className="rc-backdrop" aria-hidden="true"><div className="rc-vignette"/><div className="rc-grain"/></div>
      <AnimatePresence mode="wait" initial={false}>
        <m.section key={index} className="rc-frame" aria-live="polite"
          initial={reduce?false:{opacity:0,scale:1.025,filter:'blur(13px)'}}
          animate={{opacity:1,scale:1,filter:'blur(0px)'}}
          exit={reduce?{opacity:0}:{opacity:0,scale:.985,filter:'blur(13px)'}}
          transition={{duration:reduce?0:.75,ease:[.22,1,.36,1]}}>
          {saga?<RewindSagaScene beat={scene} recap={recap} reduce={reduce} playing={playing}/>:<FilmMoment beat={scene} recap={recap} player={story.player} reduce={reduce}/>}
        </m.section>
      </AnimatePresence>

      {!playing&&index===0&&<div className="rc-start-wrap">
        <button type="button" className="rc-start" onClick={begin}>
          <span className="rc-play-symbol">▶</span> {reduce?'EXPLORE YOUR STORY':'BEGIN YOUR REWIND'}
        </button>
        <span className="rc-start-hint">A STORY WRITTEN BY YOUR GAMES</span>
      </div>}
      {last&&<div className="rc-finale-actions">
        <button type="button" className="rc-start" onClick={restart}>↻ WATCH AGAIN</button>
        <a className="rc-finale-link" href={back}>BACK TO REWIND</a>
      </div>}

      <AnimatePresence>
        {controls&&index>0&&!last&&<m.div className="rc-chrome" initial={{opacity:0,y:12}} animate={{opacity:1,y:0}}
          exit={{opacity:0,y:12}} transition={{duration:.26}}>
          <button type="button" className="rc-action" onClick={e=>{e.stopPropagation();backward();}} aria-label="Previous chapter">←</button>
          <button type="button" className="rc-action rc-action-main" onClick={e=>{e.stopPropagation();if(reduce){forward();}else pause();}}>
            {reduce?'NEXT':playing?'PAUSE':'PLAY'} <span aria-hidden="true">{reduce?'→':playing?'Ⅱ':'▶'}</span>
          </button>
          <button type="button" className="rc-action" onClick={e=>{e.stopPropagation();forward();}} aria-label="Next chapter">→</button>
        </m.div>}
      </AnimatePresence>

      <div className={'rc-minimal-tools'+(controls||!playing?' rc-tools-visible':'')}>
        <button type="button" className="rc-close" onClick={e=>{e.stopPropagation();window.location.assign(back);}} aria-label="Exit the film">✕</button>
        <span className="rc-part" aria-label={'Chapter '+(index+1)+' of '+beats.length}>{String(index+1).padStart(2,'0')} / {String(beats.length).padStart(2,'0')}</span>
      </div>
      {index>0&&!last&&<button type="button" className={'rc-evidence-trigger'+(controls?' rc-trigger-visible':'')}
        onClick={e=>{e.stopPropagation();setEvidence(true);setPlaying(false);setChrome(true);}}>
        <span aria-hidden="true">ⓘ</span><span>THE STORY BEHIND THIS MOMENT</span>
      </button>}
      <div className={'rc-progress'+(controls?' rc-progress-active':'')} role="progressbar" aria-label="Rewind chapter progress"
        aria-valuemin={0} aria-valuemax={beats.length} aria-valuenow={index+1}>
        <span style={{width:((index+1)/beats.length*100)+'%'}}/>
      </div>

      <AnimatePresence>
        {evidence&&<m.div className="rc-evidence-scrim" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
          role="presentation" onClick={()=>setEvidence(false)}>
          <m.section role="dialog" aria-modal="true" aria-label="How this moment was calculated"
            className="rc-evidence-sheet" initial={{opacity:0,y:30}} animate={{opacity:1,y:0}} exit={{opacity:0,y:20}}
            onClick={e=>e.stopPropagation()}>
            <button type="button" className="rc-evidence-close" onClick={()=>setEvidence(false)} aria-label="Close evidence">✕</button>
            <p className="rc-sheet-kicker">BEHIND THE MOMENT</p>
            <h2>{scene.headline}</h2>
            <p>{scene.description}</p>
            <p className="rc-sheet-source">{scene.evidence}</p>
            <small>Based only on cutoff-eligible completed Season 01 games. Hypothetical rankings are not historical standings.</small>
          </m.section>
        </m.div>}
      </AnimatePresence>
    </main>
  </MotionConfig></LazyMotion>;
}

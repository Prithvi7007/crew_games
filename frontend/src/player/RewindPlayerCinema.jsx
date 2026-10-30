import React, {useCallback, useEffect, useReducer, useRef, useState} from 'react';
import {AnimatePresence, LazyMotion, MotionConfig, domAnimation, m, useReducedMotion} from 'motion/react';
import RewindDirectorScenes from './RewindDirectorScenes';
import RewindSagaScene from './RewindSagaScene';
import {ChampionCover, championAccent} from './ChampionReveal';
import {initialPlayback, playbackReducer, remainingChapterTime} from './rewindPlayback';

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
const secFor=beat=>beat?.kind==='winner'?9800:beat?.kind==='winner_badge'?8200:beat?.kind==='game_compare'
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
  const [{index,started,playing,finished},dispatch]=useReducer(playbackReducer,undefined,initialPlayback);
  const sceneClock=useRef({index:0,elapsed:0});
  const [chrome,setChrome]=useState(false);
  const [evidence,setEvidence]=useState(false);
  const hideRef=useRef(null);
  const reduce=useReducedMotion();
  const scene=beats[index];
  const last=started&&index===beats.length-1;
  const finalBadge=last&&scene?.kind==='winner_badge';
  const showCover=saga&&beats[0]?.kind==='winner'&&!started&&index===0;
  const championScene=saga&&['winner','winner_badge'].includes(scene?.kind);
  const previewPlayer=data.rewindPreviewPlayer;
  const championPreview=data.rewindChampionPreview;
  // A public player must never exit into the staff-only Film Lab.
  const back=championPreview
    ? '/rewind?preview=1&prototype=1&story=5'+(previewPlayer?'&player='+encodeURIComponent(previewPlayer):'')
    : data.rewindFilmPrototype===true
    ? '/rewind?preview=1&prototype=1&story='+(saga?'4':'3')+(previewPlayer?'&player='+encodeURIComponent(previewPlayer):'')
    : '/home';
  const tone=TONES[scene?.kind]||TONES.opening;
  const chooseChampion=event=>{
    const url=new URL(window.location.href);
    url.searchParams.set('champion',event.target.value);
    window.location.assign(url.pathname+url.search);
  };
  const go=useCallback(target=>{
    dispatch({type:'go',index:target,count:beats.length});
    setEvidence(false);
    setChrome(false);
  },[beats.length]);
  const forward=useCallback(()=>{if(last){dispatch({type:'finish'});setEvidence(false);setChrome(true);}else go(index+1);},[go,index,last]);
  const backward=useCallback(()=>go(index-1),[go,index]);
  const begin=useCallback(()=>{dispatch({type:'begin',reduced:reduce});setChrome(Boolean(reduce));},[reduce]);
  const pause=useCallback(()=>{dispatch({type:'toggle'});setChrome(true);},[]);
  const restart=useCallback(()=>{sceneClock.current={index:0,elapsed:0};dispatch({type:'restart'});setEvidence(false);setChrome(false);},[]);
  const reveal=useCallback(()=>{setChrome(true);},[]);

  // Motion timers are tied to the active chapter and are cancelled on every
  // transition, unmount, manual pause and evidence disclosure.
  useEffect(()=>{
    if(sceneClock.current.index!==index)sceneClock.current={index,elapsed:0};
    if(!playing||reduce||(last&&!finalBadge)||evidence||!scene)return undefined;
    const began=window.performance.now();
    const remaining=remainingChapterTime(scene.kind,secFor(scene),sceneClock.current.elapsed);
    const t=window.setTimeout(()=>dispatch(last?{type:'finish'}:{type:'go',index:index+1,count:beats.length}),remaining);
    return ()=>{
      window.clearTimeout(t);
      if(sceneClock.current.index===index)sceneClock.current.elapsed+=window.performance.now()-began;
    };
  },[playing,reduce,index,last,finalBadge,evidence,scene,beats.length]);
  useEffect(()=>{if(last&&(!finalBadge||reduce))dispatch({type:'finish'});},[last,finalBadge,reduce]);
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
      else if(e.code==='Space'){e.preventDefault();if(!started)begin();else pause();}
    };
    window.addEventListener('keydown',handler);
    return ()=>window.removeEventListener('keydown',handler);
  },[forward,backward,begin,pause,started]);
  if(!scene)return <main className="rc-empty"><h1>No season story yet.</h1><a href={back}>Back to Rewind</a></main>;
  const controls=chrome||!playing;
  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user">
    <main className={'rc-film rc-'+scene.kind+(playing?' rc-is-playing':'')+(saga?' saga-film':'')+(championPreview?' saga-champion-demo':'')+(showCover?' rc-showing-cover':'')+(finished?' rc-is-finished':'')} style={{'--rc-light':tone[0],'--rc-glow':tone[1],...(championScene?{'--champion-accent':championAccent(scene)}:{})}}
      aria-label={(championPreview?'Champion animation preview for ':'Season 01 cinematic Rewind for ')+story.player}
      onPointerMove={e=>{if(e.pointerType==='mouse')reveal();}}
      onPointerDown={e=>{if(e.pointerType==='touch'&&!e.target.closest('button,a,select'))setChrome(v=>!v);}}
      onFocusCapture={reveal}>
      {championPreview&&<aside className="rc-champion-preview" aria-label="Animation demo controls">
        <strong>ANIMATION DEMO · NO AWARD GRANTED</strong>
        <select aria-label="Champion animation preview" value={championPreview.selection} onChange={chooseChampion}>
          {championPreview.options.map(option=><option key={option.key} value={option.key}>{option.label}</option>)}
        </select>
      </aside>}
      {/* Saga CSS is loaded in the document head with a content fingerprint. */}
      <div className="rc-backdrop" aria-hidden="true"><div className="rc-vignette"/><div className="rc-grain"/></div>
      <AnimatePresence mode="wait" initial={false}>
        <m.section key={showCover?'cover':index} className="rc-frame" aria-live="polite"
          initial={reduce?false:{opacity:0,scale:1.025,filter:'blur(13px)'}}
          animate={{opacity:1,scale:1,filter:'blur(0px)'}}
          exit={reduce?{opacity:0}:{opacity:0,scale:.985,filter:'blur(13px)'}}
          transition={{duration:reduce?0:.75,ease:[.22,1,.36,1]}}>
          {showCover?<ChampionCover player={recap.username}/>:saga?<RewindSagaScene beat={scene} recap={recap} reduce={reduce} playing={playing}/>:<FilmMoment beat={scene} recap={recap} player={story.player} reduce={reduce}/>}
        </m.section>
      </AnimatePresence>

      {!started&&index===0&&<div className="rc-start-wrap">
        <button type="button" className="rc-start" onClick={begin}>
          <span className="rc-play-symbol">▶</span> {reduce?'EXPLORE YOUR STORY':'BEGIN YOUR REWIND'}
        </button>
        <span className="rc-start-hint">A STORY WRITTEN BY YOUR GAMES</span>
      </div>}
      {last&&finished&&<div className="rc-finale-actions">
        <button type="button" className="rc-start" onClick={restart}>↻ WATCH AGAIN</button>
        <a className="rc-finale-link" href={back}>BACK TO REWIND</a>
      </div>}

      <AnimatePresence>
        {controls&&started&&(!last||!finished)&&<m.div className="rc-chrome" initial={{opacity:0,y:12}} animate={{opacity:1,y:0}}
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
        onClick={e=>{e.stopPropagation();setEvidence(true);dispatch({type:'pause'});setChrome(true);}}>
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
            <small>{championPreview
              ? 'Animation preview only. Real scores, rankings, and badge awards are unchanged.'
              : 'Based only on cutoff-eligible completed Season 01 games. Hypothetical rankings are not historical standings.'}</small>
          </m.section>
        </m.div>}
      </AnimatePresence>
    </main>
  </MotionConfig></LazyMotion>;
}

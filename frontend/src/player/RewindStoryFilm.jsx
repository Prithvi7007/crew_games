import React, {useEffect, useState} from 'react';
import {AnimatePresence, LazyMotion, MotionConfig, domAnimation, m, useReducedMotion} from 'motion/react';

const ACCENTS = {
  opening:'#7cd8ff', rivalry:'#b2adff', swing:'#64e2c6',
  pivot:'#ffc978', strength:'#6ddcfc', standout:'#c79cff',
  momentum:'#f4afc3', consistency:'#a0e6be', ending:'#d2c1ff',
};
const PHASE_TIME = 6600;

function StoryVisual({beat, recap}) {
  const visual=beat.visual || {};
  const rival=visual.rival;
  if (beat.kind==='rivalry' && rival) {
    const max=Math.max(1,rival.myTotal,rival.theirTotal);
    return <div className="rewind-v2-rival-visual" aria-label="Final points comparison">
      <div className="rewind-v2-rival-row">
        <span>YOU</span><strong>{rival.myTotal.toLocaleString()}</strong>
        <div className="rewind-v2-track"><m.div initial={{width:0}} animate={{width:(100*rival.myTotal/max)+'%'}} transition={{duration:1.25}}/></div>
      </div>
      <div className="rewind-v2-rival-row">
        <span>{rival.name}</span><strong>{rival.theirTotal.toLocaleString()}</strong>
        <div className="rewind-v2-track"><m.div initial={{width:0}} animate={{width:(100*rival.theirTotal/max)+'%'}} transition={{duration:1.4}}/></div>
      </div>
      <p className="rewind-v2-visual-note">Final season totals · {rival.weekly.length} scheduled weeks</p>
    </div>;
  }
  if (beat.kind==='swing') {
    const {edge=0,other=0,net=0,game='One game'}=visual;
    const total=Math.max(1,edge,Math.abs(other));
    return <div className="rewind-v2-swing" aria-label="The game-by-game point difference">
      <div><span>{game.toUpperCase()}</span><strong>+{edge} pts</strong>
        <div className="rewind-v2-track"><m.div initial={{width:0}} animate={{width:(edge/total*100)+'%'}} transition={{duration:1.1}}/></div></div>
      <div><span>OTHER THREE GAMES</span><strong>{other > 0 ? '+' : ''}{other} pts</strong>
        <div className="rewind-v2-track rewind-v2-track-other"><m.div initial={{width:0}} animate={{width:(Math.abs(other)/total*100)+'%'}} transition={{duration:1.3}}/></div></div>
      <p className="rewind-v2-visual-note">Net points advantage: {net > 0 ? '+' : ''}{net} · Total game contributions, not per-attempt skill</p>
    </div>;
  }
  if (beat.kind==='pivot') {
    const current=visual.currentRank;
    const movement=Number.parseInt(beat.metric,10);
    const alternate=Number.isFinite(movement) && current ? current+movement : null;
    return <div className="rewind-v2-pivot" aria-label="Hypothetical rank comparison">
      <div><span>CURRENT {recap.finalized ? 'FINAL' : 'PREVIEW'}</span><strong>#{current || '—'}</strong></div>
      <div className="rewind-v2-pivot-line" aria-hidden="true"/>
      <div><span>WITHOUT THAT WEEK</span><strong>{alternate ? '#'+alternate : 'UNRANKED'}</strong></div>
      <p>What-if calculation · other players' totals held constant</p>
    </div>;
  }
  if (beat.kind==='consistency') {
    return <div className="rewind-v2-week-track" aria-label="Weeks with completed games">
      {(recap.weeklyScores || []).map(row=><div className={'rewind-v2-week'+(row.played?' is-active':'')} key={row.number}>
        <span>W{String(row.number).padStart(2,'0')}</span><m.i initial={{scaleY:0}} animate={{scaleY:1}} transition={{delay:row.number*.08,duration:.5}}/>
      </div>)}
    </div>;
  }
  if (beat.kind==='standout') {
    const [winners,people]=String(beat.metric).split('/').map(v=>Number(v.trim()));
    return <div className="rewind-v2-dots" aria-label="Others outscored on the same challenge">
      {Number.isFinite(people) && people >= 3 && people <= 50
        ? Array.from({length:people},(_,i)=><m.span key={i} initial={{scale:0,opacity:0}} animate={{scale:1,opacity:i<winners?1:.25}} transition={{delay:i*.06,duration:.5}}/>)
        : <span className="rewind-v2-glyph">✳</span>}
      <p className="rewind-v2-visual-note">Each dot represents another player who completed the same puzzle</p>
    </div>;
  }
  if (beat.kind==='momentum') {
    return <div className="rewind-v2-momentum" aria-label="Same-game adjusted half-season change">
      <div><span>FIRST HALF</span><i/></div>
      <svg viewBox="0 0 420 105" preserveAspectRatio="none" aria-hidden="true"><path d={beat.metric.startsWith('-')?'M 12 20 Q 210 55 408 91':'M 12 91 Q 210 55 408 20'} /></svg>
      <div><span>SECOND HALF</span><i/></div>
    </div>;
  }
  return <div className="rewind-v2-aura" aria-hidden="true">
    <div className="rewind-v2-orbit rewind-v2-orbit-outer"/>
    <div className="rewind-v2-orbit rewind-v2-orbit-inner"/>
    <span>{beat.kind==='ending'?'✳':beat.kind==='strength'?'◇':'✦'}</span>
  </div>;
}

export default function RewindStoryFilm({data}) {
  const recap=data.rewind || {};
  const story=recap.cinematicStory || {beats:[],title:'Your Season 01',player:recap.username};
  const beats=story.beats || [];
  const [index,setIndex]=useState(0);
  const [playing,setPlaying]=useState(false);
  const reduce=useReducedMotion();
  const beat=beats[index];
  const last=index===beats.length-1;
  const back='/rewind?preview=1&prototype=1&analysis=1'+
    (data.rewindPreviewPlayer?'&player='+encodeURIComponent(data.rewindPreviewPlayer):'');
  const previous=()=>{setPlaying(false);setIndex(i=>Math.max(0,i-1));};
  const next=()=>{setPlaying(false);setIndex(i=>Math.min(beats.length-1,i+1));};
  useEffect(()=>{
    if(!playing || reduce || last || beats.length<2) return undefined;
    const timer=window.setTimeout(()=>setIndex(i=>Math.min(beats.length-1,i+1)),PHASE_TIME);
    return ()=>window.clearTimeout(timer);
  },[playing,reduce,index,last,beats.length]);
  useEffect(()=>{if(last)setPlaying(false);},[last]);
  useEffect(()=>{
    const handle=e=>{
      if(['INPUT','TEXTAREA','BUTTON'].includes(document.activeElement?.tagName)) return;
      if(e.key==='ArrowRight'){e.preventDefault();next();}
      if(e.key==='ArrowLeft'){e.preventDefault();previous();}
    };
    window.addEventListener('keydown',handle);
    return ()=>window.removeEventListener('keydown',handle);
  },[beats.length]);
  if(!beat) return <main className="rewind-v2-empty"><p>No eligible season story is available.</p><a href={back}>Open research preview</a></main>;
  const accent=ACCENTS[beat.kind]||'#7cd8ff';
  const toggle=()=>{
    if(last){setIndex(0);setPlaying(!reduce);}
    else if(!playing){if(index===0)setIndex(1);setPlaying(!reduce);}
    else setPlaying(false);
  };

  return <LazyMotion features={domAnimation} strict><MotionConfig reducedMotion="user">
    <main className={'rewind-v2 rewind-v2-'+beat.kind} style={{'--rewind-v2-accent':accent}}>
      <div className="rewind-v2-background" aria-hidden="true"/>
      <header className="rewind-v2-header">
        <div className="rewind-v2-brand">CREW<span>+</span><small>REWIND / SEASON 01</small></div>
        <span className="rewind-v2-private">{recap.finalized?'FINALIZED':'UNFINALIZED PREVIEW'} · {story.player} · STAFF ONLY</span>
        <a className="rewind-v2-close" href={back} aria-label="Return to the evidence report">✕</a>
      </header>
      <nav className="rewind-v2-timeline" aria-label="Story moments">
        {beats.map((item,i)=><button type="button" key={i} aria-label={'Moment '+(i+1)+': '+item.eyebrow}
          aria-current={i===index?'step':undefined} onClick={()=>{setIndex(i);setPlaying(false);}}>
          <span className="rewind-v2-progress"><m.i animate={{scaleX:i<index?1:i===index&&playing&&!reduce?1:0}}
            initial={false} transition={{duration:i===index&&playing&&!reduce?PHASE_TIME/1000:0,ease:'linear'}}/></span>
        </button>)}
      </nav>
      <section className="rewind-v2-stage" aria-live="polite" aria-label="Personalized season discovery">
        <div className="rewind-v2-content">
          <AnimatePresence mode="sync" initial={false}>
            <m.div key={'copy-'+index} className="rewind-v2-narrative"
              initial={reduce?false:{opacity:0,y:30,filter:'blur(9px)'}}
              animate={{opacity:1,y:0,filter:'blur(0px)'}}
              exit={reduce?{opacity:0}:{opacity:0,y:-24,filter:'blur(8px)'}}
              transition={{duration:reduce?0:.72,ease:[.2,.7,.2,1]}}>
              <p className="rewind-v2-eyebrow"><span>0{index+1} / 0{beats.length}</span>{beat.eyebrow}</p>
              <h1>{beat.headline}</h1>
              <p className="rewind-v2-story">{beat.description}</p>
              <p className="rewind-v2-evidence">{beat.evidence}</p>
            </m.div>
          </AnimatePresence>
        </div>
        <div className="rewind-v2-artwork">
          <AnimatePresence mode="sync" initial={false}>
            <m.div key={'scene-'+index} className="rewind-v2-scene"
              initial={reduce?false:{opacity:0,scale:.94,x:32,filter:'blur(13px)'}}
              animate={{opacity:1,scale:1,x:0,filter:'blur(0px)'}}
              exit={reduce?{opacity:0}:{opacity:0,scale:1.04,x:-30,filter:'blur(10px)'}}
              transition={{duration:reduce?0:.85,ease:[.2,.7,.2,1]}}>
              <span className="rewind-v2-halo" aria-hidden="true"/>
              <div className="rewind-v2-number">{beat.metric}</div>
              <StoryVisual beat={beat} recap={recap}/>
            </m.div>
          </AnimatePresence>
        </div>
      </section>
      <footer className="rewind-v2-footer">
        <p>THE DETAILS MADE THE DIFFERENCE <span>· {story.title}</span></p>
        <div className="rewind-v2-actions">
          <button type="button" onClick={previous} disabled={index===0} aria-label="Previous story moment">←</button>
          <button type="button" className="rewind-v2-play" onClick={toggle}>{last?'Watch again':playing?'Pause':'Play my story'} <span aria-hidden="true">{playing?'Ⅱ':'→'}</span></button>
          <button type="button" onClick={next} disabled={last} aria-label="Next story moment">→</button>
        </div>
      </footer>
    </main>
  </MotionConfig></LazyMotion>;
}

import {remainingChapterTime} from './rewindPlayback.js';

export const COMPARE_STEP_MS=3800;
const READABLE_COMPARE_MS=1800;

export function chapterDuration(beat) {
  if(beat?.kind==='winner')return 9800;
  if(beat?.kind==='winner_badge')return 8200;
  if(beat?.kind==='game_compare')return READABLE_COMPARE_MS+
    Math.max(1,(beat.visual?.games||[]).filter(g=>g.mine!==null).length)*COMPARE_STEP_MS;
  return Math.min(11000,Math.max(7200,6800+(beat?.headline?.length||0)*30));
}

export const comparisonIndex=(elapsed,count)=>Math.max(0,Math.min(count-1,Math.floor(elapsed/COMPARE_STEP_MS)));
export const comparisonSeek=(index,still=false)=>index*COMPARE_STEP_MS+(still?READABLE_COMPARE_MS:0);
export const initialChapterTime=(beat,animated)=>animated?0:beat?.kind==='game_compare'?READABLE_COMPARE_MS:chapterDuration(beat);

export function resumeChapterTime(beat,elapsed,still) {
  if(!still)return elapsed;
  if(beat.kind!=='game_compare')return 0;
  const count=(beat.visual?.games||[]).filter(g=>g.mine!==null).length;
  return comparisonSeek(comparisonIndex(elapsed,count));
}

// Motion renders the shared elapsed value; the application owns progression.
// One cleanup cancels both drivers, including callbacks already queued by a host.
export function runChapterClock({elapsed,duration,animate,schedule,cancel,onFinish}) {
  let active=true;
  const remaining=remainingChapterTime(duration,elapsed.get());
  const animation=remaining>0?animate(elapsed,duration,{duration:remaining/1000,ease:'linear'}):null;
  const timer=schedule(()=>{
    if(!active)return;
    active=false;
    animation?.stop();
    elapsed.set(duration);
    onFinish();
  },remaining);
  return ()=>{active=false;cancel(timer);animation?.stop();};
}

import test from 'node:test';
import assert from 'node:assert/strict';
import {chapterDuration, comparisonIndex, comparisonSeek, initialChapterTime, resumeChapterTime, runChapterClock} from '../src/player/rewindTimeline.js';

// Only the external frame driver and wall clock are deterministic substitutes.
// The real Rewind clock owns deadlines, cancellation, seeks and completion.
function harness(initial=0) {
  let now=0, current=initial, finished=0;
  const tasks=new Set(), animations=new Set();
  const elapsed={get:()=>current,set:value=>{current=value;}};
  const animate=(value,target,options)=>{
    const animation={from:value.get(),target,start:now,duration:options.duration*1000,stopped:false,
      stop(){this.stopped=true;}};
    assert.equal(options.ease,'linear');
    animations.add(animation);
    return animation;
  };
  const schedule=(callback,delay)=>{const task={callback,at:now+delay};tasks.add(task);return task;};
  const cancel=task=>tasks.delete(task);
  const render=()=>{for(const a of animations)if(!a.stopped)elapsed.set(a.from+(a.target-a.from)*Math.min(1,(now-a.start)/a.duration));};
  const advance=(ms,frames=true)=>{
    const end=now+ms;
    for(;;){
      const next=[...tasks].filter(t=>t.at<=end).sort((a,b)=>a.at-b.at)[0];
      if(!next)break;
      now=next.at;if(frames)render();tasks.delete(next);next.callback();
    }
    now=end;if(frames)render();
  };
  return {elapsed,tasks,advance,get finished(){return finished;},
    run:duration=>runChapterClock({elapsed,duration,animate,schedule,cancel,onFinish:()=>{finished++;}})};
}

test('pausing freezes motion and chapter advancement; resuming uses only the remainder',()=>{
  const h=harness();
  const stop=h.run(17000);
  h.advance(4300);stop();
  assert.equal(h.elapsed.get(),4300);
  h.advance(60000);
  assert.equal(h.elapsed.get(),4300);
  assert.equal(h.finished,0);
  h.run(17000);
  h.advance(12699);assert.equal(h.finished,0);
  h.advance(1);
  assert.equal(h.finished,1);
  assert.equal(h.elapsed.get(),17000);
});

test('a cancelled deadline cannot advance a replacement chapter',()=>{
  const h=harness();
  const stop=h.run(9800);
  const stale=[...h.tasks][0].callback;
  h.advance(2300);stop();stop();
  h.elapsed.set(0);h.run(8200);
  stale();assert.equal(h.finished,0);
  assert.equal(h.elapsed.get(),0);
  h.advance(8200);assert.equal(h.finished,1);
});

test('a game selection seeks both the visible spotlight and its chapter deadline',()=>{
  const h=harness();
  const stop=h.run(17000);
  h.advance(7000);
  assert.equal(comparisonIndex(h.elapsed.get(),4),1);
  stop();h.elapsed.set(comparisonSeek(0,false));h.run(17000);
  assert.equal(comparisonIndex(h.elapsed.get(),4),0);
  h.advance(3799);assert.equal(comparisonIndex(h.elapsed.get(),4),0);
  h.advance(1);assert.equal(comparisonIndex(h.elapsed.get(),4),1);
  h.advance(11400);assert.equal(comparisonIndex(h.elapsed.get(),4),3);
  assert.equal(h.finished,0);
  h.advance(1800);assert.equal(h.finished,1);
});

test('the application deadline holds the full reveal even if the last render frame is late',()=>{
  const h=harness();h.run(9800);
  h.advance(9800,false);
  assert.equal(h.elapsed.get(),9800);
  assert.equal(h.finished,1);
  h.advance(30000);assert.equal(h.finished,1);
});

test('an animation reaching its target does not independently advance the chapter',()=>{
  const h=harness();h.run(8200);
  h.elapsed.set(8200);assert.equal(h.finished,0);
  h.advance(8200);assert.equal(h.finished,1);
});

test('paused or reduced-motion comparisons start with a complete first game, not the last one',()=>{
  const beat={kind:'game_compare',visual:{games:[{mine:80},{mine:0},{mine:null},{mine:64}]}};
  assert.equal(chapterDuration(beat),13200);
  assert.equal(initialChapterTime(beat,true),0);
  assert.equal(initialChapterTime(beat,false),1800);
  assert.equal(comparisonIndex(initialChapterTime(beat,false),3),0);
  assert.equal(comparisonSeek(2,true),9400);
  assert.equal(comparisonIndex(comparisonSeek(2,true),3),2);
});

test('comparison boundaries include zero scores and clamp at the final game',()=>{
  assert.equal(comparisonIndex(-10,4),0);
  assert.equal(comparisonIndex(3799,4),0);
  assert.equal(comparisonIndex(3800,4),1);
  assert.equal(comparisonIndex(99999,4),3);
  assert.equal(comparisonIndex(1000,0),0);
});

test('a new paused champion or badge is immediately readable',()=>{
  assert.equal(initialChapterTime({kind:'winner'},false),9800);
  assert.equal(initialChapterTime({kind:'winner_badge'},false),8200);
});

test('playing a paused visit replays its reveal instead of immediately skipping it',()=>{
  assert.equal(resumeChapterTime({kind:'winner'},9800,true),0);
  assert.equal(resumeChapterTime({kind:'weekly_trend'},7600,true),0);
  assert.equal(resumeChapterTime({kind:'game_compare',visual:{games:[{mine:80},{mine:0},{mine:64}]}},9400,true),7600);
  assert.equal(resumeChapterTime({kind:'winner'},2300,false),2300);
});

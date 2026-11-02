import test from 'node:test';
import assert from 'node:assert/strict';
import {masterChoreography, weeklyPeak, OPENING_SIGNOFF_MS, openingAwardCue, openingAwardOffset, openingCelebrationStart} from '../src/player/rewindChoreography.js';
import {chapterDuration} from '../src/player/rewindTimeline.js';

test('each master resolves its motif before the winner, then leaves a readable hold',()=>{
  const games=['mystery','trivia','word','tick_tock'];
  const starts=new Set();
  for(const gameKey of games){
    const cue=masterChoreography(gameKey);
    assert.ok(cue.badge<cue.impact && cue.impact<cue.title && cue.title<cue.winners);
    assert.ok(cue.winners+750<=cue.signoff);
    const duration=chapterDuration({kind:'season_game_master',visual:{gameKey,winners:[{}]}});
    assert.ok(duration-cue.signoff-700>=3000,gameKey+' needs three seconds after its last reveal');
    starts.add(cue.impact);
  }
  assert.equal(starts.size,4);
});

test('shared winners retain extra reading time and unknown games have a safe cue',()=>{
  const visual={gameKey:'word',winners:[{}]};
  const single=chapterDuration({kind:'season_game_master',visual});
  const shared=chapterDuration({kind:'season_game_master',visual:{...visual,winners:[{},{},{}]}});
  assert.equal(shared-single,2000);
  assert.deepEqual(masterChoreography('future-game'),masterChoreography('trivia'));
});

test('peak highlight uses the supplied real week including a zero score',()=>{
  const weeks=[{week:1,mine:0},{week:2,mine:75}];
  assert.deepEqual(weeklyPeak(weeks,1),{week:1,score:0,index:0});
  assert.deepEqual(weeklyPeak(weeks,2),{week:2,score:75,index:1});
  assert.equal(weeklyPeak(weeks,3),null);
  assert.equal(weeklyPeak([],1),null);
});

test('personal opening celebrates its final emblem and holds every completed title',()=>{
  const awards=[{badge:{}},...['trivia','word','mystery','tick_tock'].map(gameKey=>({gameKey}))];
  for(const chosen of [[awards[0]],[awards[2]],awards]){
    const impact=openingCelebrationStart(chosen);
    for(const [index,award] of chosen.entries()){
      const cue=openingAwardCue(award);
      assert.ok(impact>=openingAwardOffset(index)+cue.impact);
      assert.ok(OPENING_SIGNOFF_MS+650>=openingAwardOffset(index)+cue.winners+650);
    }
    const duration=chapterDuration({kind:'champion_opening',visual:{awards:chosen}});
    assert.ok(duration-OPENING_SIGNOFF_MS-650>=3000);
  }
});

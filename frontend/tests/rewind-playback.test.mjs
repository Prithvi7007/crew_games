import test from 'node:test';
import assert from 'node:assert/strict';
import * as playback from '../src/player/rewindPlayback.js';
const {initialPlayback, playbackReducer} = playback;
const state=(overrides={})=>({index:0,started:true,playing:true,finished:false,...overrides});

test('the winner stays behind the cover until the viewer starts', () => {
  const initial=initialPlayback();
  assert.deepEqual(initial,{index:0,started:false,playing:false,finished:false});
  assert.deepEqual(playbackReducer(initial,{type:'go',index:1,count:10}),initial);
  assert.deepEqual(playbackReducer(initial,{type:'begin',reduced:false}),state());
});

test('reduced motion begins with the first winner, with no autoplay', () => {
  assert.deepEqual(playbackReducer(initialPlayback(),{type:'begin',reduced:true}),state({playing:false}));
});

test('pausing the first winner does not restore its cover or finish the film', () => {
  const paused=playbackReducer(state(),{type:'toggle'});
  assert.deepEqual(paused,state({playing:false}));
  assert.deepEqual(playbackReducer(paused,{type:'toggle'}),state());
});

test('paused navigation back to the first act stays started and paused', () => {
  const previous=playbackReducer(state({index:1,playing:false}),{type:'go',index:0,count:10});
  assert.deepEqual(previous,state({playing:false}));
});

test('the final badge can play, pause and resume before the film finishes', () => {
  const last=playbackReducer(state(),{type:'go',index:1,count:2});
  assert.deepEqual(last,state({index:1}));
  const paused=playbackReducer(last,{type:'toggle'});
  assert.deepEqual(paused,state({index:1,playing:false}));
  assert.deepEqual(playbackReducer(paused,{type:'toggle'}),last);
  const ended=playbackReducer(last,{type:'finish'});
  assert.deepEqual(ended,state({index:1,playing:false,finished:true}));
  assert.deepEqual(playbackReducer(ended,{type:'toggle'}),ended);
});

test('browsing to the end while paused gives a completed still', () => {
  assert.deepEqual(playbackReducer(state({playing:false}),{type:'go',index:1,count:2}),
    state({index:1,playing:false,finished:true}));
});

test('opening evidence pauses without marking the story finished', () => {
  assert.deepEqual(playbackReducer(state({index:1}),{type:'pause'}),
    state({index:1,playing:false}));
});

test('navigation is bounded', () => {
  assert.deepEqual(playbackReducer(state(),{type:'go',index:999,count:10}),state({index:9}));
  assert.deepEqual(playbackReducer(state(),{type:'go',index:-1,count:10}),state());
});

test('replay restores the neutral cover', () => {
  const replayed=playbackReducer(state({index:9,playing:false,finished:true}),{type:'restart'});
  assert.deepEqual(replayed,initialPlayback());
  assert.deepEqual(playbackReducer(replayed,{type:'begin',reduced:false}),state());
});

test('every chapter resumes from its remaining time rather than starting over', () => {
  assert.equal(playback.remainingChapterTime(9800,2300),7500);
  assert.equal(playback.remainingChapterTime(8200,9000),0);
  assert.equal(playback.remainingChapterTime(17000,15000),2000);
  assert.equal(playback.remainingChapterTime(7600,6000),1600);
});

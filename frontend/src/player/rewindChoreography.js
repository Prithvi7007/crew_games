// Shared by the visual cues and chapter deadline: the reveal always has a hold.
const MASTER_CUES=Object.freeze({
  mystery:Object.freeze({badge:1400,impact:2050,title:2300,winners:2800,signoff:3600,duration:8000}),
  trivia:Object.freeze({badge:1150,impact:1800,title:2100,winners:2600,signoff:3400,duration:7800}),
  word:Object.freeze({badge:1900,impact:2550,title:2800,winners:3300,signoff:4100,duration:8500}),
  tick_tock:Object.freeze({badge:1500,impact:2150,title:2400,winners:2900,signoff:3700,duration:8100}),
});

export const masterChoreography=game=>MASTER_CUES[game]||MASTER_CUES.trivia;
const SEASON_CUE=Object.freeze({badge:600,impact:1250,title:1500,winners:2000});
export const OPENING_SIGNOFF_MS=6100;
export const openingAwardOffset=index=>2000+index*160;
export const openingAwardCue=award=>{
  const game=award.gameKey||award.badge?.gameKey;
  return game?masterChoreography(game):SEASON_CUE;
};
// A combined opening celebrates when the final emblem lands, never before it.
export const openingCelebrationStart=awards=>Math.max(0,...awards.map((award,index)=>
  openingAwardOffset(index)+openingAwardCue(award).impact));

// The server chooses the peak (including tie policy); never recalculate a winner.
export function weeklyPeak(weeks,bestWeek){
  const index=weeks.findIndex(week=>week.week===bestWeek);
  return index<0?null:{week:weeks[index].week,score:weeks[index].mine,index};
}

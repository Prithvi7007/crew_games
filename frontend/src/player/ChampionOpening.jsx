import React, {useState} from 'react';
import {useTransform} from 'motion/react';
import {Reveal} from './RewindMotion';
import ChampionCelebration, {ChampionBadgeMotion} from './ChampionCelebration';
import ChampionStageLights, {ChampionLine} from './ChampionTheater';
import {championAccent} from './ChampionReveal';
import {BadgeMedallion} from './TrophyRoom';
import MasterSignature from './MasterSignature';
import {OPENING_SIGNOFF_MS, openingAwardCue, openingAwardOffset, openingCelebrationStart} from './rewindChoreography';

const number=n=>Number(n).toLocaleString('en-US');

function OpeningAward({award,index,time,reduce}){
  const localTime=useTransform(()=>Math.max(0,time.get()-openingAwardOffset(index)));
  const game=award.gameKey||award.badge.gameKey;
  const cue=openingAwardCue(award);
  return <div className="champion-opening-award" role="listitem">
    <div className="champion-opening-medallion" style={{'--champion-accent':championAccent({visual:award})}}>
      {game&&<MasterSignature game={game} time={localTime} cue={cue} reduce={reduce}/>}
      <Reveal time={localTime} start={cue.badge} duration={650} className="champion-opening-badge">
        <ChampionBadgeMotion time={localTime} closeup={false} reduce={reduce} start={cue.badge} impact={cue.impact}>
          <BadgeMedallion badge={award.badge} size="normal" seasonNumber={1}/>
        </ChampionBadgeMotion>
      </Reveal>
    </div>
    <Reveal as="h2" time={localTime} start={cue.title} duration={650}>{award.badge.name}</Reveal>
    <Reveal as="p" time={localTime} start={cue.winners} duration={650}>{number(award.points)} <small>PTS</small>{award.shared&&<span>SHARED TITLE</span>}</Reveal>
  </div>;
}

export default function ChampionOpening({beat,recap,reduce,playing,time}) {
  const [still]=useState(()=>!playing);
  const awards=beat.visual.awards;
  return <div className={'champion-stage champion-opening'+(reduce?' is-reduced':'')+(still?' is-still':'')}
    data-awards={awards.length} aria-label="Your season championships"
    style={{'--champion-accent':championAccent(beat)}}>
    <ChampionStageLights time={time} reduce={reduce}/>
    <ChampionCelebration time={time} closeup={false} reduce={reduce} start={openingCelebrationStart(awards)}/>
    <div className="champion-copy">
      <Reveal as="p" time={time} start={350} duration={450} className="champion-kicker">CREW / SEASON 01</Reveal>
      <ChampionLine time={time} start={800} reduce={reduce} className="champion-name">{recap.username}</ChampionLine>
      <Reveal as="p" time={time} start={1750} duration={550} className="champion-opening-count">
        {awards.length===1?'YOUR SEASON TITLE':awards.length+' TITLES. ONE SEASON.'}
      </Reveal>
    </div>
    <div className="champion-opening-awards" role="list" aria-label="Earned championship titles">
      {awards.map((award,index)=><OpeningAward key={award.badge.code} award={award} index={index} time={time} reduce={reduce}/>)}
    </div>
    <Reveal as="p" time={time} start={OPENING_SIGNOFF_MS} duration={650} className="champion-signoff">YOUR SEASON. YOUR STORY.</Reveal>
  </div>;
}


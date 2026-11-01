import React, {useState} from 'react';
import {Reveal} from './RewindMotion';
import ChampionCelebration, {ChampionBadgeMotion} from './ChampionCelebration';
import ChampionStageLights, {ChampionLine} from './ChampionTheater';
import {championAccent} from './ChampionReveal';
import {BadgeMedallion} from './TrophyRoom';

const number=n=>Number(n).toLocaleString('en-US');

export default function ChampionOpening({beat,recap,reduce,playing,time}) {
  const [still]=useState(()=>!playing);
  const awards=beat.visual.awards;
  return <div className={'champion-stage champion-opening'+(reduce?' is-reduced':'')+(still?' is-still':'')}
    data-awards={awards.length} aria-label="Your season championships"
    style={{'--champion-accent':championAccent(beat)}}>
    <ChampionStageLights time={time} reduce={reduce}/>
    <ChampionCelebration time={time} closeup={false} reduce={reduce}/>
    <div className="champion-copy">
      <Reveal as="p" time={time} start={350} duration={450} className="champion-kicker">CREW / SEASON 01</Reveal>
      <ChampionLine time={time} start={800} reduce={reduce} className="champion-name">{recap.username}</ChampionLine>
      <Reveal as="p" time={time} start={1750} duration={550} className="champion-opening-count">
        {awards.length===1?'YOUR SEASON TITLE':awards.length+' TITLES. ONE SEASON.'}
      </Reveal>
    </div>
    <div className="champion-opening-awards" role="list" aria-label="Earned championship titles">
      {awards.map((award,index)=><Reveal time={time} start={2300+index*160} duration={650}
        key={award.badge.code} className="champion-opening-award" role="listitem">
        <div className="champion-opening-medallion" style={{'--champion-accent':championAccent({visual:award})}}>
          <ChampionBadgeMotion time={time} closeup={false} reduce={reduce}>
            <BadgeMedallion badge={award.badge} size="normal" seasonNumber={1}/>
          </ChampionBadgeMotion>
        </div>
        <h2>{award.badge.name}</h2>
        <p>{number(award.points)} <small>PTS</small>{award.shared&&<span>SHARED TITLE</span>}</p>
      </Reveal>)}
    </div>
    <Reveal as="p" time={time} start={5100} duration={650} className="champion-signoff">YOUR SEASON. YOUR STORY.</Reveal>
  </div>;
}

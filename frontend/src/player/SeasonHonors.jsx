import React from 'react';
import {m, useTransform} from 'motion/react';
import {Reveal} from './RewindMotion';
import {BadgeMedallion} from './TrophyRoom';
import ChampionCelebration, {ChampionBadgeMotion} from './ChampionCelebration';
import ChampionStageLights, {ChampionLine} from './ChampionTheater';
import MasterSignature from './MasterSignature';
import {masterChoreography} from './rewindChoreography';

const COLORS={mystery:'var(--crew-game-mystery,#55e6ac)',trivia:'var(--crew-game-trivia,#ffbd45)',word:'var(--crew-game-word,#55b9ff)',tick_tock:'var(--crew-game-tick-tock,#c55cff)'};
const number=n=>Number(n).toLocaleString('en-US');

function PodiumPlace({entry,time}) {
  // Final geometry stays fixed while only the platform rises beneath the names.
  const start={1:2550,2:1500,3:550}[entry.place];
  const scaleY=useTransform(time,[start,start+1100],[0,1]);
  const shared=entry.players.length>1;
  return <li className={'honors-place honors-place-'+entry.place} aria-label={'Place '+entry.place+(shared?', shared':'')}>
    <Reveal time={time} start={start+300} duration={800} className="honors-players">
      {shared&&<small className="honors-shared">SHARED PLACE</small>}
      {entry.players.map(player=><div key={player.profileId} className={'honors-player'+(player.you?' is-you':'')}>
        <strong>{player.name}</strong>{player.you&&<small className="honors-you">YOU</small>}
      </div>)}
      <p className="honors-points">{number(entry.points)} <small>PTS</small></p>
    </Reveal>
    <div className="honors-platform">
      <m.div className="honors-platform-fill" aria-hidden="true" style={{scaleY,transformOrigin:'bottom'}}/>
      <Reveal time={time} start={start+450} duration={650} className="honors-place-number">{String(entry.place).padStart(2,'0')}</Reveal>
    </div>
  </li>;
}

export function SeasonPodium({visual,time,reduce}) {
  return <div className="season-honors honors-podium" style={{'--champion-accent':COLORS.trivia}} aria-label="Season 01 overall podium">
    <ChampionStageLights time={time} reduce={reduce}/>
    <ChampionCelebration time={time} closeup={false} reduce={reduce} start={3650}/>
    <header className="honors-heading"><span className="saga-kicker">CREW / SEASON 01</span>
      <Reveal as="h1" time={time} start={100}>The season podium.</Reveal>
      <Reveal as="p" time={time} start={500}>A season of points. A place at the top.</Reveal>
    </header>
    <ol className="honors-podium-grid">
      {(visual.podium||[]).map(entry=><PodiumPlace key={entry.place} entry={entry} time={time}/>)}
    </ol>
    <Reveal as="p" className="honors-footnote" time={time} start={4100}>FINAL SEASON POINTS · EQUAL TOTALS SHARE A PLACE</Reveal>
  </div>;
}

export function SeasonGameMaster({visual,time,reduce}) {
  const winners=visual.winners||[];
  const cue=masterChoreography(visual.gameKey);
  return <div className="season-honors honors-master" data-game={visual.gameKey}
    style={{'--champion-accent':COLORS[visual.gameKey]||COLORS.trivia}} aria-label={visual.badge?.name+' announcement'}>
    <ChampionCelebration time={time} closeup reduce={reduce} start={cue.impact}/>
    <Reveal as="p" time={time} start={150} className="saga-kicker">SEASON 01 / {visual.gameName}</Reveal>
    <div className="honors-master-stage">
      <MasterSignature game={visual.gameKey} time={time} cue={cue} reduce={reduce}/>
      <Reveal time={time} start={cue.badge} duration={650} className="honors-master-badge">
        <ChampionBadgeMotion time={time} closeup reduce={reduce} start={cue.badge} impact={cue.impact}>
          <BadgeMedallion badge={visual.badge} size="normal" seasonNumber={1}/>
        </ChampionBadgeMotion>
      </Reveal>
    </div>
    <ChampionLine time={time} start={cue.title} duration={650} reduce={reduce}>{visual.badge?.name}</ChampionLine>
    <Reveal time={time} start={cue.winners} duration={750} className="honors-master-winners">
      {winners.map(winner=><div key={winner.profileId}>
        <strong>{winner.name}</strong><span>{number(winner.points)} <small>PTS</small></span>
      </div>)}
    </Reveal>
    <Reveal as="p" time={time} start={cue.signoff} className="honors-footnote">{winners.length>1?'A SHARED TITLE. A SEASON TO REMEMBER.':'A GAME MASTER. A SEASON TO REMEMBER.'}</Reveal>
  </div>;
}


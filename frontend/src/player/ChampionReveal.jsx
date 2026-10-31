import React, {useState} from 'react';
import {m,useTransform} from 'motion/react';
import {Reveal} from './RewindMotion';
import {BadgeMedallion, badgeFromAwardCode} from './TrophyRoom';

const COLORS = {
  mystery:'var(--crew-game-mystery,#55e6ac)',
  trivia:'var(--crew-game-trivia,#ffbd45)',
  word:'var(--crew-game-word,#55b9ff)',
  tick_tock:'var(--crew-game-tick-tock,#c55cff)',
};
const NAMES = {mystery:'MYSTERY', trivia:'TRIVIA', word:'WORDLE', tick_tock:'TICK-TOCK'};

export function championAccent(beat) {
  const v=beat?.visual||{};
  return COLORS[v.gameKey||v.badge?.gameKey]||'var(--crew-game-trivia,#ffbd45)';
}

export function ChampionCover({player}) {
  return <div className="champion-cover" aria-label="Rewind opening">
    <p className="champion-cover-kicker">CREW REWIND <span>SEASON 01</span></p>
    <h1>Every game.<br/><em>Led here.</em></h1>
    <div className="champion-cover-footer"><span>{player}</span><small>PRESS PLAY. RELIVE YOUR SEASON.</small></div>
  </div>;
}

export default function ChampionReveal({beat,recap,reduce,playing,time}) {
  const [still]=useState(()=>!playing);
  const overture=useTransform(time,[0,400,1200,1800],[0,1,1,0]);
  const v=beat.visual||{};
  const closeup=beat.kind==='winner_badge';
  const game=v.gameKey||v.badge?.gameKey;
  const source=v.badge||badgeFromAwardCode(v.badgeCode);
  const badge=source?{...source,gameKey:game,vertical:'leaderboard'}:null;
  const theme={'--champion-accent':championAccent(beat),'--champion-play':playing?'running':'paused'};
  const caption=v.provisional?(v.shared?'CURRENTLY SHARING THE LEAD':game?'CURRENTLY LEADING '+NAMES[game]:'CURRENTLY LEADING THE CREW'):v.shared?'A SHARED FIRST PLACE':game?'YOU LED '+NAMES[game]:'YOU LED THE CREW';
  return <div className={'champion-stage '+(closeup?'champion-closeup':'champion-winner')+(reduce?' is-reduced':'')+(still?' is-still':'')}
    style={theme} data-game={game||'season'} aria-label={closeup?'Championship badge reveal':'Champion reveal'}>
    {closeup?<>
      <Reveal as="p" time={time} start={closeup?150:1450} duration={700} className="champion-kicker">{v.demo?'THE BADGE REVEAL':'YOUR CHAMPIONSHIP BADGE'}</Reveal>
      {badge&&<Reveal as="div" time={time} start={closeup?350:1600} duration={1500} className="champion-insignia"><BadgeMedallion badge={badge} size="normal" seasonNumber={1}/></Reveal>}
      <Reveal as="h1" time={time} start={850} duration={800} className="champion-badge-name">{badge?.name||beat.headline}</Reveal>
      <Reveal as="p" time={time} start={1200} duration={800} className="champion-badge-owner">{recap.username}<span>SEASON 01</span></Reveal>
      <Reveal as="p" time={time} start={closeup?1550:3450} duration={700} className="champion-signoff">{v.provisional?'PROVISIONAL · NO AWARD GRANTED':v.demo?'ANIMATION PREVIEW':'EARNED. PRESERVED. YOURS.'}</Reveal>
    </>:<>
      <m.p style={{opacity:overture}} className="champion-overture" aria-hidden="true">{game?'YOUR GAME. YOUR MOMENT.':'SIX WEEKS IN THE MAKING.'}</m.p>
      <div className="champion-lockup">
        <div className="champion-copy">
          <Reveal as="p" time={time} start={closeup?150:1450} duration={700} className="champion-kicker">CREW / SEASON 01</Reveal>
          <Reveal as="h1" time={time} start={1900} duration={1050} className="champion-name">{recap.username}</Reveal>
          <Reveal as="h2" time={time} start={2400} duration={850} className="champion-title">{beat.headline}</Reveal>
          <Reveal as="p" time={time} start={2900} duration={700} className="champion-result">{caption}</Reveal>
        </div>
        {badge&&<Reveal as="div" time={time} start={closeup?350:1600} duration={1500} className="champion-insignia" aria-label={badge.name+' badge'}>
          <BadgeMedallion badge={badge} size="normal" seasonNumber={1}/>
          <span className="champion-badge-season">SEASON 01</span>
        </Reveal>}
      </div>
      <Reveal as="p" time={time} start={closeup?1550:3450} duration={700} className="champion-signoff">{v.provisional?'CURRENT LEADER · RESULTS NOT FINAL':v.demo?'CHAMPIONSHIP ANIMATION PREVIEW':'A TITLE EARNED. A MOMENT TO KEEP.'}</Reveal>
    </>}
  </div>;
}

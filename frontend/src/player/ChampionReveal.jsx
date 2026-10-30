import React from 'react';
import {m} from 'motion/react';
import {BadgeMedallion, badgeFromAwardCode} from './TrophyRoom';

const COLORS = {
  mystery:'var(--crew-game-mystery,#55e6ac)',
  trivia:'var(--crew-game-trivia,#ffbd45)',
  word:'var(--crew-game-word,#55b9ff)',
  tick_tock:'var(--crew-game-tick-tock,#c55cff)',
};
const NAMES = {mystery:'MYSTERY', trivia:'TRIVIA', word:'WORDLE', tick_tock:'TICK-TOCK'};
// One Motion timeline coordinates the medal, copy, and final championship seal.
const ceremony={
  hidden:{opacity:1},
  show:{opacity:1,transition:{staggerChildren:.32,delayChildren:.22}},
};
const copy={
  hidden:{opacity:0,y:22},
  show:{opacity:1,y:0,transition:{duration:.75,ease:[.22,1,.36,1]}},
};
const medal={
  hidden:{opacity:0,y:38,scale:.78,rotate:-7},
  show:{opacity:1,y:0,scale:1,rotate:0,transition:{type:'spring',stiffness:125,damping:17,mass:1.1}},
};

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

export default function ChampionReveal({beat,recap,reduce,playing}) {
  const v=beat.visual||{};
  const closeup=beat.kind==='winner_badge';
  const game=v.gameKey||v.badge?.gameKey;
  const source=v.badge||badgeFromAwardCode(v.badgeCode);
  const badge=source?{...source,gameKey:game,vertical:'leaderboard'}:null;
  const theme={'--champion-accent':championAccent(beat),'--champion-play':playing?'running':'paused'};
  const caption=v.shared?'A SHARED FIRST PLACE':game?'YOU LED '+NAMES[game]:'YOU LED THE CREW';
  return <m.div className={'champion-stage is-motion '+(closeup?'champion-closeup':'champion-winner')+(reduce?' is-reduced':'')}
    style={theme} data-game={game||'season'} aria-label={closeup?'Championship badge reveal':'Champion reveal'}
    variants={ceremony} initial={reduce?false:'hidden'} animate="show">
    {closeup?<>
      <m.p variants={copy} className="champion-kicker">{v.demo?'THE BADGE REVEAL':'YOUR CHAMPIONSHIP BADGE'}</m.p>
      {badge&&<m.div variants={medal} className="champion-insignia"><BadgeMedallion badge={badge} size="normal" seasonNumber={1}/></m.div>}
      <m.h1 variants={copy} className="champion-badge-name">{badge?.name||beat.headline}</m.h1>
      <m.p variants={copy} className="champion-badge-owner">{recap.username}<span>SEASON 01</span></m.p>
      <m.p variants={copy} className="champion-signoff">{v.demo?'ANIMATION PREVIEW':'EARNED. PRESERVED. YOURS.'}</m.p>
    </>:<>
      <m.p variants={copy} className="champion-overture" aria-hidden="true">{game?'YOUR GAME. YOUR MOMENT.':'SIX WEEKS IN THE MAKING.'}</m.p>
      <div className="champion-lockup">
        <div className="champion-copy">
          <m.p variants={copy} className="champion-kicker">CREW / SEASON 01</m.p>
          <m.h1 variants={copy} className="champion-name">{recap.username}</m.h1>
          <m.h2 variants={copy} className="champion-title">{beat.headline}</m.h2>
          <m.p variants={copy} className="champion-result">{caption}</m.p>
        </div>
        {badge&&<m.div variants={medal} className="champion-insignia" aria-label={badge.name+' badge'}>
          <BadgeMedallion badge={badge} size="normal" seasonNumber={1}/>
          <span className="champion-badge-season">SEASON 01</span>
        </m.div>}
      </div>
      <m.p variants={copy} className="champion-signoff">{v.demo?'CHAMPIONSHIP ANIMATION PREVIEW':'A TITLE EARNED. A MOMENT TO KEEP.'}</m.p>
    </>}
  </m.div>;
}

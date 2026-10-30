import React, {useState} from 'react';
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

export default function ChampionReveal({beat,recap,reduce,playing}) {
  const [still]=useState(()=>!playing);
  const v=beat.visual||{};
  const closeup=beat.kind==='winner_badge';
  const game=v.gameKey||v.badge?.gameKey;
  const source=v.badge||badgeFromAwardCode(v.badgeCode);
  const badge=source?{...source,gameKey:game,vertical:'leaderboard'}:null;
  const theme={'--champion-accent':championAccent(beat),'--champion-play':playing?'running':'paused'};
  const caption=v.shared?'A SHARED FIRST PLACE':game?'YOU LED '+NAMES[game]:'YOU LED THE CREW';
  return <div className={'champion-stage '+(closeup?'champion-closeup':'champion-winner')+(reduce?' is-reduced':'')+(still?' is-still':'')}
    style={theme} data-game={game||'season'} aria-label={closeup?'Championship badge reveal':'Champion reveal'}>
    {closeup?<>
      <p className="champion-kicker">{v.demo?'THE BADGE REVEAL':'YOUR CHAMPIONSHIP BADGE'}</p>
      {badge&&<div className="champion-insignia"><BadgeMedallion badge={badge} size="normal" seasonNumber={1}/></div>}
      <h1 className="champion-badge-name">{badge?.name||beat.headline}</h1>
      <p className="champion-badge-owner">{recap.username}<span>SEASON 01</span></p>
      <p className="champion-signoff">{v.demo?'ANIMATION PREVIEW':'EARNED. PRESERVED. YOURS.'}</p>
    </>:<>
      <p className="champion-overture" aria-hidden="true">{game?'YOUR GAME. YOUR MOMENT.':'SIX WEEKS IN THE MAKING.'}</p>
      <div className="champion-lockup">
        <div className="champion-copy">
          <p className="champion-kicker">CREW / SEASON 01</p>
          <h1 className="champion-name">{recap.username}</h1>
          <h2 className="champion-title">{beat.headline}</h2>
          <p className="champion-result">{caption}</p>
        </div>
        {badge&&<div className="champion-insignia" aria-label={badge.name+' badge'}>
          <BadgeMedallion badge={badge} size="normal" seasonNumber={1}/>
          <span className="champion-badge-season">SEASON 01</span>
        </div>}
      </div>
      <p className="champion-signoff">{v.demo?'CHAMPIONSHIP ANIMATION PREVIEW':'A TITLE EARNED. A MOMENT TO KEEP.'}</p>
    </>}
  </div>;
}

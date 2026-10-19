import React from 'react';
import { EquippedProfileBadge } from './TrophyRoom';

function MatchupPlayer({ player, side }) {
  const rank = Number.isInteger(player.rank) ? `#${player.rank}` : '—';
  const count = Number(player.completed) || 0;
  return <div className={`rankings-rival-player rankings-rival-player-${side}`}>
    <div className="rankings-rival-player-top">
      <span>{side === 'me' ? 'YOU' : 'YOUR RIVAL'}</span>
      <span>{rank === '—' ? 'UNRANKED' : `RANK ${rank}`}</span>
    </div>
    <div className="rankings-rival-identity">
      <div className="rankings-rival-avatar">
        {player.equippedBadge
          ? <EquippedProfileBadge badge={player.equippedBadge} avatar={player.avatar} size="compact"/>
          : <span aria-hidden="true">{player.avatar}</span>}
      </div>
      <strong title={player.username}>{player.username}</strong>
    </div>
    <div className="rankings-rival-stats">
      <div><strong>{Number(player.points) || 0}</strong><span>POINTS</span></div>
      <div><strong>{count}</strong><span>GAMES</span></div>
    </div>
  </div>;
}

/**
 * Visual-only readout of the existing filtered leaderboard. The opponent
 * comes from the same server-authorized board as the rankings rows.
 */
export default function RankingsRivalry({ matchup, panelRef }) {
  if (!matchup) return null;

  return <section className={`rankings-rivalry rivalry-${matchup.direction}`} ref={panelRef}
    id="rankings-rivalry" aria-labelledby="rankings-rivalry-title">
    <div className="rankings-rivalry-top">
      <div>
        <span className="rankings-rivalry-kicker"><span aria-hidden="true">✦</span> RIVALRY RADAR</span>
        <h2 id="rankings-rivalry-title">A little friendly competition.</h2>
        <p>Tap <strong>VS</strong> next to any player to choose your matchup.</p>
      </div>
      <span className="rankings-rivalry-fun">JUST FOR FUN</span>
    </div>
    <div className="rankings-rivalry-stage">
      <MatchupPlayer player={matchup.me} side="me"/>
      <div className="rankings-rivalry-center">
        <span className="rankings-rivalry-vs" aria-hidden="true">VS</span>
        <div className="rankings-rivalry-gap" role="status" aria-live="polite" aria-atomic="true">
          <strong>{matchup.summary}</strong>
          <span>{matchup.direction === 'tied'
            ? 'Rank order can still use tiebreakers'
            : 'In the selected rankings view'}</span>
        </div>
      </div>
      <MatchupPlayer player={matchup.rival} side="rival"/>
    </div>
    <p className="rankings-rivalry-foot">Scores reflect the selected season, week and game. Matchups never change points, badges or standings.</p>
  </section>;
}

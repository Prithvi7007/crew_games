import React from 'react';

// Four independent portals installed around a shared cinema-style viewing arc.
// Not a carousel: each game stays in its own position and remains directly accessible.
const SLOTS = ['outer-left', 'inner-left', 'inner-right', 'outer-right'];

export default function HomeTheaterArc({ games, renderCard }) {
  if (!games.length) return null;

  return <section className="crew-theater-arc" aria-label="This week's CREW games">
    <div className="crew-theater-arc-stage">
      <div className="crew-theater-arc-ambient" aria-hidden="true" />
      {games.map((game, index) => <div
        key={game.key}
        className={`crew-theater-arc-panel is-${SLOTS[index] || 'inner-right'}`}
      >
        {renderCard(game, index)}
      </div>)}
    </div>
  </section>;
}

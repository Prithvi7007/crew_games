import React from 'react';

// A fixed 3D gallery, not a carousel: every game stays visible and directly accessible.
const POSITIONS = ['outer-left', 'inner-left', 'inner-right', 'outer-right'];

export default function HomeCoverflow({ games, renderCard }) {
  if (!games.length) return null;

  return <section className="crew-coverflow" aria-label="This week's CREW games">
    <div className="crew-coverflow-stage">
      <div className="crew-coverflow-atmosphere" aria-hidden="true" />
      {games.map((game, index) => <div
        key={game.key}
        className={`crew-coverflow-item is-${POSITIONS[index] || 'inner-right'}`}
      >
        {renderCard(game, index)}
      </div>)}
    </div>
  </section>;
}

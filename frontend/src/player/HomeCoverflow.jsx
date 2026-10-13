import React, { useEffect, useRef, useState } from 'react';

// Independent desktop-only carousel. Slot positions stay in a bounded stage,
// unlike transforms applied to the homepage's four-column grid.
const POSITIONS = ['outer-left', 'inner-left', 'inner-right', 'outer-right'];

export default function HomeCoverflow({ games, renderCard }) {
  const [offset, setOffset] = useState(0);
  const [wrappedKey, setWrappedKey] = useState(null);
  const pointerStart = useRef(null);
  const suppressClick = useRef(false);
  const total = games.length;

  useEffect(() => {
    if (!wrappedKey) return undefined;
    const timer = window.setTimeout(() => setWrappedKey(null), 560);
    return () => window.clearTimeout(timer);
  }, [wrappedKey, offset]);

  function move(direction) {
    if (total < 2) return;
    const wrappedIndex = direction > 0 ? offset : (offset + total - 1) % total;
    setWrappedKey(games[wrappedIndex].key);
    setOffset(current => (current + direction + total) % total);
  }

  function onPointerDown(event) {
    if (event.button !== 0) return;
    pointerStart.current = { x: event.clientX, y: event.clientY };
  }

  function onPointerUp(event) {
    const start = pointerStart.current;
    pointerStart.current = null;
    if (!start) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    if (Math.abs(dx) < 55 || Math.abs(dx) < Math.abs(dy) * 1.3) return;
    // Swiping should never accidentally open a game card.
    suppressClick.current = true;
    move(dx < 0 ? 1 : -1);
    window.setTimeout(() => { suppressClick.current = false; }, 0);
  }

  function onKeyDown(event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      move(1);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      move(-1);
    }
  }

  if (!total) return null;

  return <section
    className="crew-coverflow"
    aria-label="This week's games, interactive card carousel"
    aria-roledescription="carousel"
    onKeyDown={onKeyDown}
  >
    <div className="crew-coverflow-stage"
      onDragStart={event => event.preventDefault()}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
      onPointerCancel={() => { pointerStart.current = null; }}
      onClickCapture={event => {
        if (suppressClick.current) {
          event.preventDefault();
          event.stopPropagation();
          suppressClick.current = false;
        }
      }}
    >
      {games.map((game, index) => {
        const slot = (index - offset + total) % total;
        const position = POSITIONS[slot] || 'inner-right';
        return <div
          key={game.key}
          className={`crew-coverflow-item is-${position}${game.key === wrappedKey ? ' is-wrapping' : ''}`}
          data-slot={position}
          aria-label={`${game.title}, position ${slot + 1} of ${total}`}
        >
          {renderCard(game, index)}
        </div>;
      })}
    </div>
    <div className="crew-coverflow-controls">
      <button type="button" onClick={() => move(-1)} aria-label="Rotate game cards left">‹ <span>Previous</span></button>
      <div className="crew-coverflow-dots" aria-label="Choose carousel position">
        {games.map((game, index) => <button
          type="button"
          key={game.key}
          className={index === offset ? 'is-active' : ''}
          aria-label={`Start with ${game.title}`}
          aria-pressed={index === offset}
          onClick={() => { setWrappedKey(null); setOffset(index); }}
        ><span /></button>)}
      </div>
      <button type="button" onClick={() => move(1)} aria-label="Rotate game cards right"><span>Next</span> ›</button>
    </div>
    <span className="crew-coverflow-announcement" role="status" aria-live="polite">
      {games[offset]?.title} starts the carousel
    </span>
  </section>;
}

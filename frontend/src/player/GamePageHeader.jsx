import React from 'react';

/**
 * One visual header for every CREW game, using the approved Trivia Tuesday
 * structure and existing v19 header styles. Game-specific mechanics, stage
 * design and right-hand metric are supplied as data, not separate markup.
 */
export default function GamePageHeader({
  title,
  description,
  dateLabel,
  returnUrl,
  archive = false,
  metricValue,
  metricLabel,
  metricDecorative = false,
}) {
  return (
    <header className="v19-trivia-heading crew-game-heading">
      <div className="v19-trivia-heading-copy">
        <div className="v19-trivia-context crew-game-context">
          <a className="v19-back-link" href={returnUrl} aria-label={archive ? 'Back to game archive' : 'Back to home'}>← Back</a>
          <span className="v19-trivia-date">{dateLabel}</span>
        </div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {metricValue != null && (
        <div className="v19-trivia-heading-mark" aria-hidden={metricDecorative ? 'true' : undefined}>
          <span>{metricValue}</span>
          <small>{metricLabel}</small>
        </div>
      )}
    </header>
  );
}

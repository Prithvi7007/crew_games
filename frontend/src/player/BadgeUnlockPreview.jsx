import React, { useEffect, useMemo, useState } from 'react';
import { BadgeMedallion, badgeFromAwardCode } from './TrophyRoom';

// These are illustrative catalog choices, never claimed as earned or sent to an API.
const PRESETS = Object.freeze([
  { key: 'common', label: 'Common', codes: ['case_closed'], description: 'Solved the mystery within three clues.' },
  { key: 'rare', label: 'Rare', codes: ['sharp_instincts'], description: 'Solved the mystery with only two clues.' },
  { key: 'epic', label: 'Epic', codes: ['mind_reader'], description: 'Cracked the mystery on the first clue.' },
  { key: 'legendary', label: 'Legendary', codes: ['one_shot_wonder'], description: 'Solved Wordle Wednesday on the first guess.' },
  { key: 'double', label: '2 badges', codes: ['case_closed', 'sharp_instincts'], description: 'Two achievements. One extraordinary round.' },
  { key: 'triple', label: '3 badges', codes: ['case_closed', 'sharp_instincts', 'mind_reader'], description: 'Three achievements. One extraordinary round.' },
]);
const RANK = { common: 0, rare: 1, epic: 2, legendary: 3 };

function revealDetails(preset) {
  const badges = preset.codes.map(badgeFromAwardCode).filter(Boolean);
  const top = [...badges].sort((a, b) => RANK[b.rarity] - RANK[a.rarity])[0];
  return { badges, top, multiple: badges.length > 1 };
}

function CinematicReveal({ preset, seasonNumber }) {
  const { badges, top, multiple } = useMemo(() => revealDetails(preset), [preset]);
  const [skipped, setSkipped] = useState(false);
  const [phase, setPhase] = useState('ACHIEVEMENTS DETECTED');
  const [progress, setProgress] = useState(0);
  const count = badges.length;

  useEffect(() => {
    if (skipped) {
      setProgress(count);
      setPhase('REWARDS ACQUIRED');
      return undefined;
    }
    const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) {
      setSkipped(true);
      setProgress(count);
      setPhase('REWARDS ACQUIRED');
      return undefined;
    }
    const timers = [];
    const later = (ms, fn) => timers.push(window.setTimeout(fn, ms));
    if (multiple) {
      badges.forEach((badge, index) => later(500 + index * 920, () => {
        setProgress(index + 1);
        setPhase(badge.name.toUpperCase() + ' · ' + badge.rarity.toUpperCase() + ' UNLOCKED');
      }));
      later(count === 2 ? 2560 : 3490, () => setPhase('REWARDS ACQUIRED'));
    } else {
      later(600, () => setPhase('SUMMONING YOUR REWARD'));
      later(1750, () => { setPhase(top.rarity.toUpperCase() + ' REWARD UNLOCKED'); setProgress(1); });
    }
    return () => timers.forEach(window.clearTimeout);
  }, [badges, count, multiple, top, skipped]);

  function skip() {
    setSkipped(true);
    setProgress(count);
    setPhase('REWARDS ACQUIRED');
  }

  return <section
    className={'cul-cinema cul-' + (multiple ? 'multi' : 'single') + ' cul-count-' + count + ' cul-tier-' + top.rarity + (skipped ? ' is-skipped' : ' is-playing')}
    aria-label="Cinematic badge unlock preview"
    onKeyDown={event => { if (event.key === 'Escape') skip(); }}
  >
    <div className="cul-atmosphere" aria-hidden="true"/>
    <div className="cul-grid" aria-hidden="true"/>
    <div className="cul-rays" aria-hidden="true"/>
    <div className="cul-beacon" aria-hidden="true"/>
    <div className="cul-orbit" aria-hidden="true"/>
    <div className="cul-aura" aria-hidden="true"/>
    <div className="cul-shockwave" aria-hidden="true"/>
    <div className="cul-flash" aria-hidden="true"/>
    <div className="cul-vignette" aria-hidden="true"/>
    <div className="cul-hud">
      <div><span>CREW REWARDS / SEASON {String(seasonNumber || 1).padStart(2, '0')}</span><strong>{top.gameKey === 'word' ? 'WORDLE WEDNESDAY' : 'MYSTERY MONDAY'}</strong></div>
      <div className="cul-hud-right"><span>ACHIEVEMENTS</span><strong>{String(progress).padStart(2, '0')} / {String(count).padStart(2, '0')}</strong></div>
    </div>
    <p className="cul-phase" aria-live="polite" aria-atomic="true">{phase}</p>
    <div className="cul-medals" aria-label={count + ' simulated badge unlocks'}>
      {badges.map((badge, index) => <div
        key={badge.code}
        className={'cul-medal cul-medal-' + (index + 1) + ' trophy-rarity-' + badge.rarity + ' cul-game-' + (badge.gameKey || 'mystery')}
        style={{ '--cul-sequence': index }}
      >
        <div className="cul-coin"><BadgeMedallion badge={badge} size="victory"/><div className="cul-coin-shine" aria-hidden="true"/></div>
        <span className="cul-medal-tier">{badge.rarity.toUpperCase()}</span>
      </div>)}
    </div>
    <div className="cul-particles" aria-hidden="true">
      {Array.from({ length: 28 }, (_, index) => {
        const angle = index * 2.39996;
        const radius = 125 + (index % 6) * 26;
        return <i key={index} style={{
          '--cul-tx': (Math.cos(angle) * radius).toFixed(1) + 'px',
          '--cul-ty': (Math.sin(angle) * radius).toFixed(1) + 'px',
          '--cul-particle-delay': (1.1 + (index % 6) * 0.045) + 's',
          '--cul-particle-duration': (0.85 + (index % 5) * 0.1) + 's',
        }}/>;
      })}
    </div>
    <div className="cul-message">
      <div className="cul-rarity-heading">{multiple ? 'ACHIEVEMENT COLLECTION UPDATED' : top.rarity.toUpperCase() + ' · BADGE UNLOCKED'}</div>
      <h2>{multiple ? (count === 2 ? 'DOUBLE UNLOCK' : 'TRIPLE UNLOCK') : top.name}</h2>
      <p>{preset.description}</p>
      {multiple ? <div className="cul-collection" aria-label="All simulated badges">
        {badges.map(badge => <div key={badge.code} className={'cul-collection-item trophy-rarity-' + badge.rarity}>
          <span aria-hidden="true">✦</span><div><strong>{badge.name}</strong><small>{badge.rarity.toUpperCase()}</small></div>
        </div>)}
      </div> : null}
    </div>
    <div className="cul-cinema-footer">
      <span>SIMULATION · NO AWARDS ISSUED</span>
      <button type="button" onClick={skip} disabled={skipped}>Skip animation <span aria-hidden="true">→</span></button>
    </div>
  </section>;
}

export default function BadgeUnlockPreview({ data, Header }) {
  const [selected, setSelected] = useState(2);
  const [replay, setReplay] = useState(0);
  const preset = PRESETS[selected];
  const season = data.selectedSeason?.number || 1;
  return <div className="app-shell cul-page">
    <Header shell={data.shell}/>
    <main className="cul-main">
      <div className="cul-heading">
        <div><p className="cul-eyebrow">STAFF-ONLY ANIMATION LAB</p><h1>Badge unlock cinema</h1><p>Preview the real CREW medal artwork in a cinematic reward sequence. This page cannot grant badges or modify scores.</p></div>
        <a href="/trophies" className="cul-back">← Back to Badge Collection</a>
      </div>
      <CinematicReveal key={preset.key + ':' + replay} preset={preset} seasonNumber={season}/>
      <section className="cul-panel" aria-label="Animation preview controls">
        <div><p className="cul-panel-label">CHOOSE A REWARD SCENARIO</p><div className="cul-choices">
          {PRESETS.map((choice, index) => <button
            key={choice.key} type="button"
            className={selected === index ? 'is-current' : ''}
            aria-pressed={selected === index}
            onClick={() => { setSelected(index); setReplay(value => value + 1); }}
          >{choice.label}</button>)}
        </div></div>
        <button className="cul-replay" type="button" onClick={() => setReplay(value => value + 1)}>↻ Replay reveal</button>
      </section>
      <p className="cul-footnote">Preview mode only. Sample achievements are from the official badge catalog, not your earned awards. Normal game results, unlock delivery, collections and showcase remain unchanged.</p>
    </main>
  </div>;
}
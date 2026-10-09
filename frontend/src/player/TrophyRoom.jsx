import React, { useMemo, useState } from 'react';

const FILTERS = [
  ['all', 'All badges'],
  ['game_mastery', 'Mastery'],
  ['leaderboard', 'Rivalry'],
  ['secret', 'Secret'],
  ['collection', 'Collection'],
];

const DETAILS = {
  case_closed: 'Solve Mystery Monday within 3 clues.',
  sharp_instincts: 'Solve the mystery within 2 clues.',
  mind_reader: 'Crack the mystery on the first clue.',
  sharp_shooter: 'Answer at least 8 of 10 trivia questions correctly.',
  brainiac: 'Answer at least 9 of 10 trivia questions correctly.',
  flawless_victory: 'Get all 10 trivia questions right.',
  word_wizard: 'Solve Wordle Wednesday in 4 guesses or fewer.',
  word_ninja: 'Solve the Wordle in 3 guesses or fewer.',
  one_shot_wonder: 'Solve the Wordle on your first guess.',
  close_call: 'Finish Tick-Tock within 1.00 second of the target.',
  precision_pro: 'Finish within 0.25 seconds of the target.',
  human_stopwatch: 'Finish within 0.10 seconds of the target.',
  season_champion: 'Finish the season with the most total points.',
  season_trivia_master: 'Lead the season in correct trivia answers.',
  season_wordle_master: 'Earn the best eligible Wordle average.',
  season_mystery_master: 'Earn the best eligible Mystery clue average.',
  season_tick_tock_master: 'Earn the best eligible Tick-Tock accuracy.',
  high_roller: 'Score at least 350 of 400 points in one week.',
  unicorn: 'A perfect CREW week. Four games, four perfect scores.',
  badge_hunter: 'Collect 10 different non-collection badges this season.',
  crew_legend: 'Collect 15 different non-collection badges this season.',
};

const MOTIFS = {
  case_closed: 'M25 40h46M34 24h28v33H34zM41 33h14M41 42h9',
  sharp_instincts: 'M22 50l15-17 13 12 21-26M59 19h12v12',
  mind_reader: 'M19 42q31-40 62 0-31 40-62 0zM50 29a13 13 0 1 0 0 26 13 13 0 1 0 0-26',
  sharp_shooter: 'M50 17v66M17 50h66M50 29a21 21 0 1 0 0 42 21 21 0 1 0 0-42',
  brainiac: 'M37 64c-23-10-14-30-3-31 0-18 18-18 24-10 17-4 25 13 16 23 3 16-12 24-22 16M45 26v45M34 43h11M57 41h17',
  flawless_victory: 'M28 26l12 13 30-22M26 52l12 13 30-22M30 77h40',
  word_wizard: 'M24 24h22v22H24zM54 24h22v22H54zM24 54h22v22H24zM54 54h22v22H54z',
  word_ninja: 'M24 64l15-39 11 30 14-30 12 39M30 74h42M43 38h16',
  one_shot_wonder: 'M50 17l11 23 25 4-18 18 4 25-22-12-22 12 4-25-18-18 25-4z',
  close_call: 'M50 19v13M50 68v13M19 50h13M68 50h13M50 32a18 18 0 1 0 0 36 18 18 0 1 0 0-36M50 50l10-10',
  precision_pro: 'M50 17v15M50 68v15M17 50h15M68 50h15M50 30a20 20 0 1 0 0 40 20 20 0 1 0 0-40M50 50l6-14',
  human_stopwatch: 'M40 18h20M50 18v11M70 29l8-8M50 32a23 23 0 1 0 0 46 23 23 0 1 0 0-46M50 55l10-16M43 10h14',
  season_champion: 'M26 24h48v17c0 17-12 29-24 33-12-4-24-16-24-33zM26 31H15v5c0 11 9 18 18 19M74 31h11v5c0 11-9 18-18 19M50 38l5 10 11 2-8 8 2 11-10-5-10 5 2-11-8-8 11-2z',
  season_trivia_master: 'M25 20h50v60H25zM35 33h30M35 46h22M35 59h30M36 70h15',
  season_wordle_master: 'M22 22h25v25H22zM53 22h25v25H53zM22 53h25v25H22zM53 53h25v25H53zM26 66l7 7 11-15',
  season_mystery_master: 'M32 31l8-13h20l8 13M24 34h52v30l-26 15-26-15zM39 51h22M50 40v22',
  season_tick_tock_master: 'M38 17h24M50 17v12M50 30a24 24 0 1 0 0 48 24 24 0 1 0 0-48M50 53l15-12M64 25l8-8',
  high_roller: 'M26 62l-7-26 18 9 13-25 13 25 18-9-7 26zM27 69h46M34 78h32',
  unicorn: 'M27 70l16-26-1-18 19 11 18 12-17 2-6 20-15 6zM43 26L57 9M65 60l5 6M32 40l-9-10',
  badge_hunter: 'M50 14l26 15v42L50 86 24 71V29zM35 40h30M35 50h30M35 60h20',
  crew_legend: 'M50 12l12 24 27 4-19 19 5 27-25-13-25 13 5-27-19-19 27-4zM50 37v26M37 50h26',
};

function toneFor(badge) {
  return badge.gameKey || (badge.vertical === 'secret' ? 'legendary' : 'spectrum');
}

export function BadgeMedallion({ badge, size = 'normal' }) {
  return <span className={'trophy-medallion trophy-tone-' + toneFor(badge) + ' trophy-rarity-' + badge.rarity + ' trophy-medallion-' + size} aria-hidden="true">
    <svg viewBox="0 0 100 100" focusable="false" fill="none">
      <path className="medallion-outer" d="M50 4 82 22 94 50 82 78 50 96 18 78 6 50 18 22z"/>
      <path className="medallion-inner" d="M50 13 74 27 85 50 74 73 50 87 26 73 15 50 26 27z"/>
      <path className="medallion-motif" d={MOTIFS[badge.code] || MOTIFS.badge_hunter}/>
      <circle cx="50" cy="4" r="2" fill="currentColor"/>
    </svg>
    <span className="trophy-medallion-shine"/>
  </span>;
}

function BadgeCard({ badge }) {
  const hidden = badge.vertical === 'secret' && !badge.earned;
  return <article className={'trophy-badge-card trophy-tone-' + toneFor(badge) + ' trophy-rarity-' + badge.rarity + (badge.earned ? ' is-earned' : ' is-locked')}>
    <div className="trophy-badge-top"><span>{badge.vertical === 'game_mastery' ? 'GAME MASTERY' : badge.vertical === 'leaderboard' ? 'RIVALRY' : badge.vertical.toUpperCase()}</span><span className="trophy-rarity-label">{badge.rarity.toUpperCase()}</span></div>
    <BadgeMedallion badge={badge}/>
    <div className="trophy-badge-copy"><strong>{hidden ? 'Secret achievement' : badge.name}</strong><p>{hidden ? 'A surprise worth chasing.' : DETAILS[badge.code]}</p></div>
    <div className="trophy-badge-bottom"><span>{badge.earned ? '✦ UNLOCKED' : '◇ LOCKED'}</span>{badge.earned && badge.sourceDate ? <time dateTime={badge.sourceDate}>{badge.sourceDate}</time> : null}</div>
  </article>;
}

export default function TrophyRoom({ data, Header }) {
  const [filter, setFilter] = useState('all');
  const badges = data.badges || [];
  const earned = data.earnedCount || 0;
  const season = data.selectedSeason;
  const filtered = useMemo(() => filter === 'all' ? badges : badges.filter(badge => badge.vertical === filter), [badges, filter]);
  const displayedShowcase = [1, 2, 3].map(slot => {
    const saved = (data.showcase || []).find(entry => entry.slot === slot);
    const badge = badges.find(item => item.code === saved?.badgeCode);
    return { slot, saved, badge };
  });
  return <div className="trophy-room-shell">
    <Header shell={data.shell}/>
    <main className="trophy-room-main">
      <header className="trophy-hero">
        <div className="trophy-hero-copy"><span className="trophy-eyebrow">CREW · SEASON ACHIEVEMENTS</span><h1>Make your mark<span>.</span></h1><p>Every clue solved. Every last-second save. Every perfect round. This is where your CREW moments become legend.</p>
          <div className="trophy-season-row">
            {(data.seasons || []).map(item => <a key={item.id} href={'/trophies?season=' + item.id} className={'trophy-season-chip' + (season?.id === item.id ? ' is-active' : '')} aria-current={season?.id === item.id ? 'page' : undefined}>S{String(item.number).padStart(2,'0')}</a>)}
          </div>
        </div>
        <div className="trophy-hero-stat" style={{ '--trophy-progress': String(Math.round(earned / Math.max(1, badges.length) * 100)) + '%' }}>
          <span className="trophy-stat-caption">{season ? 'SEASON ' + String(season.number).padStart(2, '0') : 'CREW'} COLLECTION</span>
          <div className="trophy-count-ring"><strong>{earned}<small> / {badges.length}</small></strong></div>
          <span className="trophy-stat-footer">BADGES UNLOCKED</span>
        </div>
      </header>
      <section className="trophy-showcase" aria-labelledby="trophy-showcase-title">
        <header className="trophy-section-header"><div><span className="trophy-eyebrow">THE FRONT ROW</span><h2 id="trophy-showcase-title">Your showcase</h2></div><p>Three badges to represent your CREW story.</p></header>
        <div className="trophy-showcase-grid">{displayedShowcase.map(({slot, saved, badge}) => <div key={slot} className={'trophy-showcase-slot' + (saved && badge ? ' is-filled' : '')}>
          <span className="trophy-slot-index">SLOT 0{slot}</span>
          {saved && badge ? <><BadgeMedallion badge={badge} size="showcase"/><strong>{badge.name}</strong><span className="trophy-showcase-rarity">{badge.rarity.toUpperCase()}</span></>
            : <><span className="trophy-empty-mark" aria-hidden="true">✧</span><strong>Open spotlight</strong><span className="trophy-slot-hint">Reserved for an earned badge</span></>}
        </div>)}</div>
        <p className="trophy-future-note">Showcase editing and automatic badge unlocks are coming in the next update. Existing earned badges are shown here.</p>
      </section>
      <section className="trophy-collection" aria-labelledby="trophy-collection-title">
        <header className="trophy-section-header"><div><span className="trophy-eyebrow">THE COMPLETE SET</span><h2 id="trophy-collection-title">The collection <small>{earned} / {badges.length} discovered</small></h2></div><p>Four rarities. Twenty-one reasons to keep playing.</p></header>
        <div className="trophy-filters" aria-label="Filter badges">{FILTERS.map(([key,label]) => <button type="button" key={key} className={'trophy-filter' + (key === filter ? ' is-active' : '')} aria-pressed={key === filter} onClick={() => setFilter(key)}>{label}<span>{key === 'all' ? badges.length : badges.filter(b => b.vertical === key).length}</span></button>)}</div>
        <div className="trophy-badge-grid">{filtered.map(badge => <BadgeCard key={badge.code} badge={badge}/>)}</div>
        <p className="trophy-collection-footnote">Season championship badges are finalized at season end. Previously earned badges remain in your season history.</p>
      </section>
    </main>
  </div>;
}

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

const MOTIFS = Object.freeze({
  case_closed: 'M31 40h38v29H31zM40 40v-9h20v9M43 53h14M43 60h14',
  sharp_instincts: 'M26 66l17-18 11 9 20-26M61 31h13v13',
  mind_reader: 'M23 50Q50 20 77 50Q50 80 23 50zM50 38a12 12 0 1 0 0 24 12 12 0 1 0 0-24',
  sharp_shooter: 'M50 25v50M25 50h50M50 31a19 19 0 1 0 0 38 19 19 0 1 0 0-38',
  brainiac: 'M50 31c-10-13-27-3-23 11-9 8-4 22 6 21 0 11 17 13 17 2M50 31c10-13 27-3 23 11 9 8 4 22-6 21 0 11-17 13-17 2M50 31v39',
  flawless_victory: 'M27 39l10 10 15-17M27 60l10 10 34-37',
  word_wizard: 'M29 71L65 35M60 28l3 7 8 2-8 3-3 8-3-8-8-3 8-2zM30 37l2-7M41 28l1-7',
  word_ninja: 'M28 47q22-25 44 0v19H28zM36 54h9M55 54h9M50 22v9',
  one_shot_wonder: 'M50 25l8 16 18 3-13 12 3 18-16-8-16 8 3-18-13-12 18-3z',
  close_call: 'M50 29a22 22 0 1 0 0 44 22 22 0 1 0 0-44M50 38v13l9 6M43 22h14',
  precision_pro: 'M50 31a21 21 0 1 0 0 42 21 21 0 1 0 0-42M50 39a13 13 0 1 0 0 26 13 13 0 1 0 0-26M50 47v10M45 52h10',
  human_stopwatch: 'M42 23h16M50 23v9M50 33a21 21 0 1 0 0 42 21 21 0 1 0 0-42M50 42v13l-8 8M65 27l7-7',
  season_champion: 'M34 29h32v30H34zM42 59v10h16V59M38 73h24',
  season_trivia_master: 'M32 32h36M32 43h24M32 54h36M32 65h20',
  season_wordle_master: 'M30 29h19v19H30zM53 29h19v19H53zM30 52h19v19H30zM53 52h19v19H53zM57 63l4 4 7-9',
  season_mystery_master: 'M45 30a17 17 0 1 0 0 34 17 17 0 1 0 0-34M58 59l16 16M40 44h10',
  season_tick_tock_master: 'M33 28h34M33 72h34M39 28v9l11 13-11 13v9M61 28v9L50 50l11 13v9',
  high_roller: 'M25 38l11 10 14-21 14 21 11-10-6 30H31zM33 73h34',
  unicorn: 'M31 73l10-19-3-20 12 9 10-18 2 20 13 9-17 5-6 14zM49 43l-2 12',
  badge_hunter: 'M50 26l22 9v19c0 12-10 22-22 27-12-5-22-15-22-27V35zM50 41l4 8 9 1-7 6 2 9-8-4-8 4 2-9-7-6 9-1z',
  crew_legend: 'M33 29h34v34L50 76 33 63zM43 42h14M50 36v26',
});

// One bold, outline-only insignia family. Shared by collection, reward and avatar.
// Minimal paths keep every achievement legible at small sizes.
function Insignia({ badge, compact = false }) {
  return <g className={'crew-insignia' + (compact ? ' is-compact' : '')}>
    <path className="medallion-motif" d={MOTIFS[badge.code] || MOTIFS.badge_hunter}/>
  </g>;
}

// Keep the victory reveal in sync with the server's fixed badge catalog.
// Only server-awarded codes are rendered as newly earned trophies.
export const BADGE_CATALOG = Object.freeze({
  case_closed: ['Case Closed', 'common', 'mystery'],
  sharp_instincts: ['Sharp Instincts', 'rare', 'mystery'],
  mind_reader: ['Mind Reader', 'epic', 'mystery'],
  sharp_shooter: ['Sharp Shooter', 'common', 'trivia'],
  brainiac: ['Brainiac', 'rare', 'trivia'],
  flawless_victory: ['Flawless Victory', 'epic', 'trivia'],
  word_wizard: ['Word Wizard', 'common', 'word'],
  word_ninja: ['Word Ninja', 'rare', 'word'],
  one_shot_wonder: ['One-Shot Wonder', 'legendary', 'word'],
  close_call: ['Close Call', 'common', 'tick_tock'],
  precision_pro: ['Precision Pro', 'rare', 'tick_tock'],
  human_stopwatch: ['Human Stopwatch', 'epic', 'tick_tock'],
  season_champion: ['Season Champion', 'legendary', null],
  season_trivia_master: ['Season Trivia Master', 'epic', null],
  season_wordle_master: ['Season Wordle Master', 'epic', null],
  season_mystery_master: ['Season Mystery Master', 'epic', null],
  season_tick_tock_master: ['Season Tick-Tock Master', 'epic', null],
  high_roller: ['High Roller', 'epic', null],
  unicorn: ['Unicorn', 'legendary', null],
  badge_hunter: ['Badge Hunter', 'epic', null],
  crew_legend: ['CREW Legend', 'legendary', null],
});

export function badgeFromAwardCode(code) {
  const entry = Object.prototype.hasOwnProperty.call(BADGE_CATALOG, code) ? BADGE_CATALOG[code] : null;
  return entry ? { code, name: entry[0], rarity: entry[1], gameKey: entry[2], vertical: code === 'unicorn' ? 'secret' : 'game_mastery' } : null;
}


// One medal grammar: the outer frame is rarity, the inner enamel is game identity.
const GAME_COLORS = Object.freeze({ mystery:'#55e6ac', trivia:'#ffbd45', word:'#55b9ff', tick_tock:'#c55cff' });
const GAME_ORDER = ['mystery', 'trivia', 'word', 'tick_tock'];
const RIVALRY_GAME = Object.freeze({
  season_mystery_master:'mystery', season_trivia_master:'trivia',
  season_wordle_master:'word', season_tick_tock_master:'tick_tock',
});
function ringSegments(badge) {
  const focus = RIVALRY_GAME[badge.code];
  if (focus) return [[focus, .5], ...GAME_ORDER.filter(key => key !== focus).map(key => [key, 1/6])];
  if (badge.gameKey && GAME_COLORS[badge.gameKey]) return [[badge.gameKey, 1]];
  return GAME_ORDER.map(key => [key, .25]);
}
function GameIdentityRing({ badge, radius = 37, className = 'medallion-inner' }) {
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return <g className={className} transform="rotate(-90 50 50)">
    {ringSegments(badge).map(([key, fraction]) => {
      const start = offset;
      offset += fraction;
      return <circle key={key} cx="50" cy="50" r={radius} fill="none"
        stroke={GAME_COLORS[key]} strokeWidth="6"
        strokeDasharray={`${fraction * circumference} ${circumference}`}
        strokeDashoffset={-start * circumference}/>;
    })}
  </g>;
}

function toneFor(badge) {
  return badge.gameKey || (badge.vertical === 'secret' ? 'legendary' : 'spectrum');
}
// Insignias use the game identity (not rarity); rivalry masters use their focus game.
function insigniaColor(badge) {
  const focus = badge.gameKey || RIVALRY_GAME[badge.code];
  if (focus && GAME_COLORS[focus]) return GAME_COLORS[focus];
  return badge.code === 'season_champion' ? '#ffbd45' : '#eef4ff';
}

export function BadgeMedallion({ badge, size = 'normal', concealed = false, seasonNumber = null }) {
  return <span style={{ '--insignia-color': insigniaColor(badge) }} className={'trophy-medallion trophy-tone-' + toneFor(badge) + ' trophy-rarity-' + badge.rarity + ' trophy-medallion-' + size + (concealed ? ' is-concealed' : '')} aria-hidden="true">
    <svg viewBox="0 0 100 100" focusable="false" fill="none">
      <circle className="medallion-outer" cx="50" cy="50" r="44"/>
      <GameIdentityRing badge={badge}/>
      <circle className="medallion-insignia-disc" cx="50" cy="50" r="29"/>{concealed ? <path className="medallion-motif" d="M38 44v-9a12 12 0 0 1 24 0v9M32 44h36v31H32zM50 56v9"/> : <Insignia badge={badge}/>}
    </svg>
  </span>;
}

export function EquippedProfileBadge({ badge, avatar }) {
  if (!badge) return <div className="v20-profile-avatar" aria-hidden="true">{avatar}</div>;
  return <div style={{ '--insignia-color': insigniaColor(badge) }} className={'crew-equipped-badge trophy-tone-' + toneFor(badge) + ' trophy-rarity-' + badge.rarity} role="img" aria-label={badge.name + ' equipped, season ' + (badge.seasonNumber ?? 'unknown')}>
    <span className="crew-equipped-avatar" aria-hidden="true">{avatar}</span>
    <svg className="crew-equipped-rings" viewBox="0 0 100 100" focusable="false" aria-hidden="true" fill="none">
      <circle className="crew-equipped-outer" cx="50" cy="50" r="46"/>
      <GameIdentityRing badge={badge} radius={39} className="crew-equipped-game-ring"/>
    </svg>
    <span className="crew-equipped-achievement" aria-hidden="true">
      <svg viewBox="0 0 100 100" fill="none" focusable="false">
        <Insignia badge={badge} compact/>
      </svg>
    </span>
    {badge.seasonNumber != null ? <span className="crew-equipped-season" aria-hidden="true">S{String(badge.seasonNumber).padStart(2, '0')}</span> : null}
  </div>;
}

function BadgeCard({ badge, seasonNumber, isEquipped, saving, onSelect }) {
  const hidden = false;
  const canEquip = Boolean(badge.earned && badge.awardId);
  const Surface = canEquip ? 'button' : 'div';
  return <article className={'trophy-badge-card trophy-tone-' + toneFor(badge) + ' trophy-rarity-' + badge.rarity + (badge.earned ? ' is-earned' : ' is-locked') + (isEquipped ? ' is-equipped' : '') + (hidden ? ' is-mysterious' : '')}>
    <Surface
      className="trophy-badge-surface"
      {...(canEquip ? {
        type: 'button',
        disabled: saving,
        'aria-pressed': isEquipped,
        'aria-label': isEquipped
          ? `${badge.name} equipped on your profile. Select again to unequip.`
          : `${badge.name} unlocked. Select to equip on your profile.`,
        onClick: () => onSelect(badge.awardId),
      } : {})}
    >
      <span className="trophy-badge-top"><span>{badge.vertical === 'game_mastery' ? 'GAME MASTERY' : badge.vertical === 'leaderboard' ? 'RIVALRY' : badge.vertical.toUpperCase()}</span><span className="trophy-rarity-label">{badge.rarity.toUpperCase()}</span></span>
      <BadgeMedallion badge={badge} concealed={hidden} seasonNumber={seasonNumber}/>
      {isEquipped ? <span className="trophy-equipped-mark" aria-hidden="true">✓</span> : null}
      <span className="trophy-badge-copy"><strong>{hidden ? 'Undiscovered achievement' : badge.name}</strong><span className="trophy-badge-description">{hidden ? 'Earn this badge to reveal its identity and story.' : DETAILS[badge.code]}</span></span>
      <span className="trophy-badge-bottom"><span>{isEquipped ? '✓ EQUIPPED' : canEquip ? '✦ EQUIP' : '◇ LOCKED'}</span>{badge.earned && badge.sourceDate ? <time dateTime={badge.sourceDate}>{badge.sourceDate}</time> : null}</span>
    </Surface>
  </article>;
}

export default function TrophyRoom({ data, Header, saveSlot, onReplayTour }) {
  const [showcase, setShowcase] = useState(data.showcase || []);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [filter, setFilter] = useState('all');
  const badges = data.badges || [];
  const earned = data.earnedCount || 0;
  const season = data.selectedSeason;
  const filtered = useMemo(() => filter === 'all' ? badges : badges.filter(badge => badge.vertical === filter), [badges, filter]);
  const equipped = showcase.find(entry => entry.slot === 1);
  const equippedBadge = equipped?.badge || badges.find(item => item.code === equipped?.badgeCode);

  async function selectBadge(awardId) {
    if (saving) return;
    const badge = badges.find(item => item.earned && item.awardId === awardId);
    if (!badge) return;
    const removing = equipped?.awardId === awardId;
    setSaving(true);
    setFeedback('');
    try {
      const result = await saveSlot(1, removing ? null : awardId);
      setShowcase(result.showcase || []);
      setFeedback(removing ? `${badge.name} removed from your profile.` : `${badge.name} equipped on your profile.`);
    } catch (error) {
      setFeedback(error?.message || 'Could not update badge. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return <div className="trophy-room-shell">
    <Header shell={data.shell}/>
    <main className="trophy-room-main">
      <header className="trophy-simple-header">
        <div><span className="trophy-eyebrow">CREW ACHIEVEMENTS</span><h1>Your badges</h1><p>Collect achievements. Select an unlocked badge to wear it.</p>{data.tourReplay && onReplayTour ? <button type="button" className="crew-tour-replay" onClick={onReplayTour}>Replay welcome tour ↗</button> : null}</div>
        <div className="trophy-season-row">
          {(data.seasons || []).map(item => <a key={item.id} href={'/trophies?season=' + item.id} className={'trophy-season-chip' + (season?.id === item.id ? ' is-active' : '')} aria-current={season?.id === item.id ? 'page' : undefined}>S{String(item.number).padStart(2,'0')}</a>)}
        </div>
      </header>
      <section className="trophy-collection" aria-labelledby="trophy-collection-title">
        <header className="trophy-section-header"><div><span className="trophy-eyebrow">ACHIEVEMENT COLLECTION</span><h2 id="trophy-collection-title">All badges <small>{earned} / {badges.length} unlocked</small></h2><p className="trophy-equip-guidance">{equippedBadge ? `Wearing: ${equippedBadge.name}. Select another unlocked badge to switch, or select the equipped badge again to remove it.` : 'Select an unlocked badge to wear it on your profile. Select it again to remove it.'}</p></div></header>
        <p className="trophy-editor-feedback trophy-collection-feedback" role="status" aria-live="polite">{feedback}</p>
        <div className="trophy-filters" aria-label="Filter badges">{FILTERS.map(([key,label]) => <button type="button" key={key} className={'trophy-filter' + (key === filter ? ' is-active' : '')} aria-pressed={key === filter} onClick={() => setFilter(key)}>{label}<span>{key === 'all' ? badges.length : badges.filter(b => b.vertical === key).length}</span></button>)}</div>
        <div className="trophy-badge-grid">{filtered.map(badge => <BadgeCard key={badge.code} badge={badge} seasonNumber={season?.number} isEquipped={Boolean(equipped?.awardId === badge.awardId)} saving={saving} onSelect={selectBadge}/>)}</div>
        <p className="trophy-collection-footnote">Season championship badges are finalized at season end. Previously earned badges remain in your season history.</p>
      </section>
    </main>
  </div>;
}

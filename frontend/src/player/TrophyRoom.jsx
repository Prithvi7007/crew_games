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


// Custom engraved accent work complements each unique central insignia.
// These details are shared by the Trophy Room, showcase and equipped avatar.
const INSIGNIA_DETAILS = Object.freeze({
  case_closed:'M31 70h38M39 75h22M63 29l7-7M66 35h9',
  sharp_instincts:'M50 20v9M50 71v9M20 50h9M71 50h9M50 17l5 9-5 6-5-6z',
  mind_reader:'M29 24l-5-6M71 24l5-6M50 17v7M32 65l-5 7M68 65l5 7',
  sharp_shooter:'M50 22v9M50 69v9M22 50h9M69 50h9M46 46h8v8h-8z',
  brainiac:'M31 30l-7-5M67 24l7-6M28 60l-8 7M65 70l7 7M51 30v36',
  flawless_victory:'M22 23l-7-7M78 23l7-7M50 16v-8M20 72l-7 7M80 72l7 7',
  word_wizard:'M30 30h10M60 30h10M30 60h10M60 60h10M49 19v62',
  word_ninja:'M25 25l-8-8M75 25l8-8M50 14v8M27 82l-7 6M73 82l7 6',
  one_shot_wonder:'M50 9v8M50 83v8M9 50h8M83 50h8M22 22l7 7M78 22l-7 7',
  close_call:'M30 25l-6-6M70 25l6-6M30 75l-6 6M70 75l6 6',
  precision_pro:'M25 25l-6-6M75 25l6-6M25 75l-6 6M75 75l6 6M50 36v-5',
  human_stopwatch:'M25 42l-7-4M75 42l7-4M25 67l-7 4M75 67l7 4M50 39v-5',
  season_champion:'M31 78h38M37 84h26M18 19l5-6M82 19l-5-6M50 10v7',
  season_trivia_master:'M18 28l-7-7M82 28l7-7M50 10v8M19 77l-7 7M81 77l7 7',
  season_wordle_master:'M50 12v7M12 50h7M81 50h7M50 81v7M29 13l-6-6M71 13l6-6',
  season_mystery_master:'M50 10v8M18 25l-7-5M82 25l7-5M18 75l-7 5M82 75l7 5',
  season_tick_tock_master:'M23 25l-7-7M77 25l7-7M23 75l-7 7M77 75l7 7',
  high_roller:'M50 9v8M19 22l7 7M81 22l-7 7M19 79l7-7M81 79l-7-7',
  unicorn:'M17 52l-8-3M25 24l-5-7M73 20l7-8M83 64l8 4M50 84v8',
  badge_hunter:'M50 8v8M15 30l7 4M85 30l-7 4M15 70l7-4M85 70l-7-4',
  crew_legend:'M50 5v7M12 23l9 6M88 23l-9 6M12 77l9-6M88 77l-9-6',
});
function Insignia({ badge, compact = false }) {
  const code = badge.code;
  return <g className={'crew-insignia' + (compact ? ' is-compact' : '')}>
    <circle className="crew-insignia-halo" cx="50" cy="50" r="27"/>
    <path className="crew-insignia-engraving" d={INSIGNIA_DETAILS[code] || INSIGNIA_DETAILS.badge_hunter}/>
    <path className="crew-insignia-shadow" d={MOTIFS[code] || MOTIFS.badge_hunter}/>
    <path className="medallion-motif" d={MOTIFS[code] || MOTIFS.badge_hunter}/>
    <circle className="crew-insignia-jewel" cx="50" cy="13" r="1.6"/>
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
        stroke={GAME_COLORS[key]} strokeWidth="3.3"
        strokeDasharray={`${fraction * circumference} ${circumference}`}
        strokeDashoffset={-start * circumference}/>;
    })}
  </g>;
}

function toneFor(badge) {
  return badge.gameKey || (badge.vertical === 'secret' ? 'legendary' : 'spectrum');
}

export function BadgeMedallion({ badge, size = 'normal', concealed = false, seasonNumber = null }) {
  return <span className={'trophy-medallion trophy-tone-' + toneFor(badge) + ' trophy-rarity-' + badge.rarity + ' trophy-medallion-' + size + (concealed ? ' is-concealed' : '')} aria-hidden="true">
    <span className="trophy-aura-field"/><svg viewBox="0 0 100 100" focusable="false" fill="none">
      <circle className="medallion-outer" cx="50" cy="50" r="44"/>
      <GameIdentityRing badge={badge}/>
      <circle className="medallion-insignia-disc" cx="50" cy="50" r="29"/>{concealed ? <path className="medallion-motif" d="M38 44v-9a12 12 0 0 1 24 0v9M32 44h36v31H32zM50 56v9"/> : <Insignia badge={badge}/>}
      <circle cx="50" cy="4" r="2" fill="currentColor"/>
    </svg>
    <span className="trophy-medallion-shine"/><span className="trophy-aura-flare trophy-aura-flare-left"/><span className="trophy-aura-flare trophy-aura-flare-right"/>

  </span>;
}

export function EquippedProfileBadge({ badge, avatar }) {
  if (!badge) return <div className="v20-profile-avatar" aria-hidden="true">{avatar}</div>;
  return <div className={'crew-equipped-badge trophy-tone-' + toneFor(badge) + ' trophy-rarity-' + badge.rarity} role="img" aria-label={badge.name + ' equipped, season ' + (badge.seasonNumber ?? 'unknown')}>
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

function BadgeCard({ badge, seasonNumber }) {
  const hidden = false;
  return <article className={'trophy-badge-card trophy-tone-' + toneFor(badge) + ' trophy-rarity-' + badge.rarity + (badge.earned ? ' is-earned' : ' is-locked') + (hidden ? ' is-mysterious' : '')}>
    <div className="trophy-badge-top"><span>{badge.vertical === 'game_mastery' ? 'GAME MASTERY' : badge.vertical === 'leaderboard' ? 'RIVALRY' : badge.vertical.toUpperCase()}</span><span className="trophy-rarity-label">{badge.rarity.toUpperCase()}</span></div>
    <BadgeMedallion badge={badge} concealed={hidden} seasonNumber={seasonNumber}/>
    <div className="trophy-badge-copy"><strong>{hidden ? 'Undiscovered achievement' : badge.name}</strong><p>{hidden ? 'Earn this badge to reveal its identity and story.' : DETAILS[badge.code]}</p></div>
    <div className="trophy-badge-bottom"><span>{badge.earned ? '✦ UNLOCKED' : '◇ LOCKED'}</span>{badge.earned && badge.sourceDate ? <time dateTime={badge.sourceDate}>{badge.sourceDate}</time> : null}</div>
  </article>;
}

export default function TrophyRoom({ data, Header, saveSlot }) {
  const [showcase, setShowcase] = useState(data.showcase || []);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [filter, setFilter] = useState('all');
  const badges = data.badges || [];
  const earned = data.earnedCount || 0;
  const season = data.selectedSeason;
  const filtered = useMemo(() => filter === 'all' ? badges : badges.filter(badge => badge.vertical === filter), [badges, filter]);
  const unlocked = badges.filter(badge => badge.earned && badge.awardId);
  const equipped = showcase.find(entry => entry.slot === 1);
  const equippedBadge = equipped?.badge || badges.find(item => item.code === equipped?.badgeCode);

  async function equipBadge(awardId) {
    if (saving) return;
    setSaving(true);
    setFeedback('');
    try {
      const result = await saveSlot(1, awardId ? Number(awardId) : null);
      setShowcase(result.showcase || []);
      setFeedback(awardId ? 'Badge selected.' : 'Badge cleared.');
    } catch (error) {
      setFeedback(error?.message || 'Could not update badge.');
    } finally {
      setSaving(false);
    }
  }

  return <div className="trophy-room-shell">
    <Header shell={data.shell}/>
    <main className="trophy-room-main">
      <header className="trophy-simple-header">
        <div><span className="trophy-eyebrow">CREW ACHIEVEMENTS</span><h1>Your badges</h1><p>Collect achievements and choose one to wear on your profile.</p></div>
        <div className="trophy-season-row">
          {(data.seasons || []).map(item => <a key={item.id} href={'/trophies?season=' + item.id} className={'trophy-season-chip' + (season?.id === item.id ? ' is-active' : '')} aria-current={season?.id === item.id ? 'page' : undefined}>S{String(item.number).padStart(2,'0')}</a>)}
        </div>
      </header>
      <section className="trophy-single-equip" aria-labelledby="trophy-equip-title">
        <div className="trophy-single-equip-preview">
          {equippedBadge ? <BadgeMedallion badge={equippedBadge} size="showcase" seasonNumber={equipped?.seasonNumber ?? season?.number}/> : <span className="trophy-empty-mark" aria-hidden="true">✧</span>}
        </div>
        <div className="trophy-single-equip-controls">
          <span className="trophy-eyebrow">PROFILE BADGE</span>
          <h2 id="trophy-equip-title">{equippedBadge ? equippedBadge.name : 'Choose your badge'}</h2>
          <p>One equipped badge appears with your profile picture.</p>
          <label htmlFor="trophy-equip-select">Equipped badge</label>
          <select id="trophy-equip-select" value={equipped?.awardId || ''} disabled={saving} onChange={event => equipBadge(event.target.value)}>
            <option value="">No badge</option>
            {equipped && !unlocked.some(item => item.awardId === equipped.awardId) ? <option value={equipped.awardId}>{equippedBadge?.name || 'Previously earned badge'}</option> : null}
            {unlocked.map(item => <option key={item.awardId} value={item.awardId}>{item.name}</option>)}
          </select>
          <p className="trophy-editor-feedback" role="status" aria-live="polite">{feedback}</p>
        </div>
      </section>
      <section className="trophy-collection" aria-labelledby="trophy-collection-title">
        <header className="trophy-section-header"><div><span className="trophy-eyebrow">ACHIEVEMENT COLLECTION</span><h2 id="trophy-collection-title">All badges <small>{earned} / {badges.length} unlocked</small></h2></div></header>
        <div className="trophy-filters" aria-label="Filter badges">{FILTERS.map(([key,label]) => <button type="button" key={key} className={'trophy-filter' + (key === filter ? ' is-active' : '')} aria-pressed={key === filter} onClick={() => setFilter(key)}>{label}<span>{key === 'all' ? badges.length : badges.filter(b => b.vertical === key).length}</span></button>)}</div>
        <div className="trophy-badge-grid">{filtered.map(badge => <BadgeCard key={badge.code} badge={badge} seasonNumber={season?.number}/>)}</div>
        <p className="trophy-collection-footnote">Season championship badges are finalized at season end. Previously earned badges remain in your season history.</p>
      </section>
    </main>
  </div>;
}

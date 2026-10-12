import React, { useEffect, useRef, useState } from 'react';
import { BadgeMedallion, EquippedProfileBadge, badgeFromAwardCode } from './TrophyRoom';

const TIERS = [
  ['Common', '#b7c3d6'], ['Rare', '#55b9ff'], ['Epic', '#b98aff'], ['Legendary', '#ffc866'],
];

export default function TrophyWelcomeTour({ tour, avatar, onClose, saveAction }) {
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const dialogRef = useRef(null);
  const returnFocusRef = useRef(null);
  const earned = tour?.badges || [];
  const featured = earned.slice(0, 8);
  const headings = ['The Trophy Room is unlocked', 'Anatomy of a CREW badge', 'Look what you have earned', 'Wear your victory'];
  const copy = [
    'Your Trophy Room vault is open. Every CREW victory now has a place to shine.',
    'Five deliberate layers make every badge yours: rarity, game identity, achievement, season and the avatar at its heart.',
    earned.length ? 'These are real achievements from your saved games. You earned every one of them.' : 'Your collection is waiting. Play your favorite CREW games to earn your first trophy.',
    'Choose an unlocked badge in the Trophy Room to wear it around your profile avatar. Switch it anytime.',
  ];

  useEffect(() => {
    returnFocusRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      returnFocusRef.current?.focus?.();
    };
  }, []);

  async function close(action) {
    if (saving) return;
    setError('');
    if (tour.preview) { onClose(); return; }
    setSaving(true);
    try {
      await saveAction(action);
      onClose();
      if (action === 'finished') window.location.assign('/trophies');
    } catch {
      // Tour failure must never prevent access to the game.
      setError('We could not save your tour choice. You can still continue playing.');
      setSaving(false);
    }
  }

  function handleKeys(event) {
    if (event.key === 'Escape') { event.preventDefault(); close('later'); }
    if (event.key !== 'Tab') return;
    const controls = [...dialogRef.current.querySelectorAll('button:not([disabled]),a[href]')];
    if (!controls.length) return;
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  return <div className="crew-tour-backdrop">
    <section className="crew-tour-dialog" role="dialog" aria-modal="true" aria-labelledby="crew-tour-title" aria-describedby="crew-tour-description" tabIndex={-1} ref={dialogRef} onKeyDown={handleKeys}>
      <button type="button" className="crew-tour-close" aria-label="Close trophy welcome tour" disabled={saving} onClick={() => close('later')}>×</button>
      <div className="crew-tour-stage" key={step}>
      <p className="crew-tour-kicker">{tour.preview ? 'PREVIEW · ' : ''}CREW TROPHY ROOM · {step + 1} / 4</p>
      <h2 id="crew-tour-title">{headings[step]}</h2>
      <p id="crew-tour-description" className="crew-tour-copy">{copy[step]}</p>
      {step === 0 ? <div className="crew-tour-vault" aria-hidden="true">
        <div className="crew-tour-vault-atmosphere"/>
        <div className="crew-tour-vault-halo is-outer"/>
        <div className="crew-tour-vault-halo is-middle"/>
        <div className="crew-tour-vault-halo is-inner"/>
        <div className="crew-tour-vault-light"/>
        <div className="crew-tour-vault-pedestal"/>
        <div className="crew-tour-vault-trophy">
          <BadgeMedallion badge={badgeFromAwardCode("badge_hunter")} size="victory"/>
        </div>
        <div className="crew-tour-vault-door is-left"/>
        <div className="crew-tour-vault-door is-right"/>
        <span className="crew-tour-vault-status">VAULT ACCESS GRANTED</span>
      </div> : null}
      {step === 1 ? <div className="crew-tour-anatomy" aria-label="CREW badge design explained">
        <div className="crew-tour-anatomy-column is-left">
          <div className="crew-tour-anatomy-note">
            <span>01 / RARITY FRAME</span>
            <p>The outer metal signals Common, Rare, Epic or Legendary.</p>
          </div>
          <div className="crew-tour-anatomy-note">
            <span>02 / GAME SIGNATURE</span>
            <p>The colored inner ring identifies which CREW game shaped the win.</p>
          </div>
        </div>
        <figure className="crew-tour-anatomy-medal">
          <div className="crew-tour-anatomy-avatar" aria-hidden="true">
            <EquippedProfileBadge badge={{ ...badgeFromAwardCode('case_closed'), seasonNumber: tour.seasonNumber || 1, preview: true }} avatar={avatar || '⭐'}/>
          </div>
          <figcaption>Illustrative example · not an earned award</figcaption>
        </figure>
        <div className="crew-tour-anatomy-column is-right">
          <div className="crew-tour-anatomy-note">
            <span>03 / ACHIEVEMENT MARK</span>
            <p>The upper-right symbol celebrates the exact milestone earned.</p>
          </div>
          <div className="crew-tour-anatomy-note">
            <span>04 / SEASON STAMP</span>
            <p>The lower-right S-number records the season of the achievement.</p>
          </div>
        </div>
        <div className="crew-tour-anatomy-center-note">
          <span>05 / YOUR AVATAR</span>
          <p>The player stays at the center. Every achievement frames your identity, never replaces it.</p>
        </div>
        <div className="crew-tour-anatomy-rarities" aria-label="Rarity frame colors">
          {TIERS.map(([name, color]) => <span key={name} style={{'--tier-color': color}}><i aria-hidden="true"/>{name}</span>)}
        </div>
      </div> : null}
      {step === 2 ? <div>
        <strong className="crew-tour-count" aria-label={tour.earnedCount + ' earned badges'}>{tour.earnedCount} <small>/ 21</small></strong>
        <span className="crew-tour-kicker">SEASON {tour.seasonNumber || '—'} ACHIEVEMENTS</span>
        {featured.length ? <div className="crew-tour-badges" aria-label="Your earned badges">{featured.map((badge, index) => <div className="crew-tour-badge" style={{'--badge-index': index}} key={badge.code}><BadgeMedallion badge={badge}/><strong>{badge.name}</strong></div>)}</div> : <div className="crew-tour-art"><BadgeMedallion badge={badgeFromAwardCode("case_closed")} concealed/></div>}
        {earned.length > featured.length ? <p className="crew-tour-copy">And {earned.length - featured.length} more waiting in your collection.</p> : null}
      </div> : null}
      {step === 3 ? <div className="crew-tour-profile">
        <div className="crew-tour-wearing" aria-hidden="true">
          <EquippedProfileBadge badge={{ ...(earned[0] || badgeFromAwardCode('case_closed')), seasonNumber: tour.seasonNumber || 1, preview: !earned.length }} avatar={avatar || '⭐'}/>
        </div>
        <p>{earned.length ? 'Your earned badge, ready to wear.' : 'Preview of how a future achievement will frame your avatar.'}</p>
      </div> : null}
      </div>
      <div className="crew-tour-progress" aria-label={'Step ' + (step + 1) + ' of 4'}>{headings.map((_, index) => <span key={index} className={index === step ? 'is-active' : ''}/>)}</div>
      {error ? <p className="crew-tour-error" role="alert">{error} <button type="button" className="crew-tour-secondary" onClick={onClose}>Continue without saving</button></p> : null}
      <div className="crew-tour-actions">
        {step > 0 ? <button type="button" className="crew-tour-secondary" disabled={saving} onClick={() => setStep(step - 1)}>Back</button> : null}
        <button type="button" className="crew-tour-primary" disabled={saving} onClick={() => step < 3 ? setStep(step + 1) : close('finished')}>{step === 0 ? 'Discover trophies →' : step < 3 ? 'Next →' : 'Enter my Trophy Room →'}</button>
        <button type="button" className="crew-tour-secondary" disabled={saving} onClick={() => close(step === 0 ? 'later' : 'skipped')}>{step === 0 ? 'Maybe later' : 'Skip tour'}</button>
      </div>
    </section>
  </div>;
}

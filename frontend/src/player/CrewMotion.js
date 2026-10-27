/**
 * CREW entrance motion: a tiny, dependency-free enhancement for static
 * authenticated page sections. The UI remains fully visible and usable if
 * JavaScript, IntersectionObserver, or Web Animations are unavailable.
 *
 * Never animate gameplay choices, live ranking updates, dialogs or badges
 * currently being awarded: state changes there must stay immediate.
 */
export const CREW_ENTRANCE_SELECTOR = [
  '.v17-intro.home-summary',
  '.rewind-home-invite',
  '.v22-today-desktop .v22-feature',
  '.v22-today-desktop .v22-week-progress',
  '.v22-today-desktop .v22-week-grid',
  '.games-main > .crew-page-head',
  '.games-week-block',
  '.rankings-head',
  '.v20-profile-hero',
  '.v20-stat-strip',
  '.v20-settings > .v20-panel',
  '.trophy-hero',
  '.trophy-showcase',
  '.trophy-collection',
].join(', ');

const ENTRANCE_FRAMES = [
  { opacity: 0.3, transform: 'translate3d(0, 12px, 0)' },
  { opacity: 1, transform: 'translate3d(0, 0, 0)' },
];

const animated = new WeakSet();

export function enableCrewEntranceMotion(root) {
  if (!root || typeof window === 'undefined') return () => {};
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  if (media?.matches || document.visibilityState === 'hidden') return () => {};
  if (!window.IntersectionObserver || typeof Element === 'undefined' ||
      typeof Element.prototype.animate !== 'function') return () => {};

  const sections = Array.from(root.querySelectorAll(CREW_ENTRANCE_SELECTOR))
    .filter(node => !animated.has(node) && node.getClientRects().length > 0)
    .slice(0, 32);

  if (!sections.length) return () => {};

  const animations = new Set();
  const observer = new window.IntersectionObserver(entries => {
    if (media?.matches) return;
    for (const entry of entries) {
      if (!entry.isIntersecting || animated.has(entry.target)) continue;
      observer.unobserve(entry.target);
      animated.add(entry.target);
      const section = entry.target;
      const index = sections.indexOf(section);
      // Readable timing: at most three subtle stagger steps, never a long wait.
      const delay = Math.min(index % 4, 3) * 35;
      const handle = section.animate(ENTRANCE_FRAMES, {
        duration: 360,
        delay,
        easing: 'cubic-bezier(.2, .7, .2, 1)',
        fill: 'none',
      });
      animations.add(handle);
      handle.finished.then(
        () => animations.delete(handle),
        () => animations.delete(handle),
      );
    }
  }, { threshold: 0.08, rootMargin: '0px 0px -20px 0px' });

  sections.forEach(section => observer.observe(section));

  function cancelMotion() {
    observer.disconnect();
    animations.forEach(handle => handle.cancel());
    animations.clear();
  }
  function onPreferenceChange() {
    if (media?.matches) cancelMotion();
  }

  media?.addEventListener?.('change', onPreferenceChange);
  return () => {
    media?.removeEventListener?.('change', onPreferenceChange);
    cancelMotion();
  };
}

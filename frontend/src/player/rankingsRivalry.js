/**
 * A purely presentational matchup: read the scores already returned for the
 * active leaderboard filters. No extra player lookup, stored rivalry, or score
 * writes. Server-provided order remains the source of truth for rank.
 */
export function rivalryModel(board, preferredId = null) {
  const players = Array.isArray(board?.players) ? board.players : [];
  const me = board?.me ?? players.find(player => player.me);
  if (!me || me.profile_id == null) return null;

  const rivals = players.filter(
    player => player.profile_id != null
      && String(player.profile_id) !== String(me.profile_id)
      && Number(player.points) > 0
  );
  if (!rivals.length) return null;

  let rival = preferredId == null
    ? undefined
    : rivals.find(player => String(player.profile_id) === String(preferredId));

  if (!rival) {
    const selfIndex = players.findIndex(
      player => String(player.profile_id) === String(me.profile_id)
    );
    // Chase the player just ahead. Leaders compare with the closest challenger.
    // An unranked player starts with the lowest-scoring ranked opponent.
    rival = selfIndex > 0
      ? players[selfIndex - 1]
      : selfIndex === 0
        ? rivals[0]
        : rivals[rivals.length - 1];
  }

  const mine = Number(me.points) || 0;
  const theirs = Number(rival.points) || 0;
  const gap = Math.abs(mine - theirs);
  const direction = mine > theirs ? 'ahead' : mine < theirs ? 'behind' : 'tied';
  const summary = direction === 'ahead'
    ? `You're ${gap} point${gap === 1 ? '' : 's'} ahead`
    : direction === 'behind'
      ? `${gap} point${gap === 1 ? '' : 's'} to tie`
      : 'Tied on points';

  return { me, rival, direction, gap, summary };
}

(() => {
  const root = document.querySelector('[data-leaderboard]'); if (!root) return;
  const period = document.getElementById('leader-period'), game = document.getElementById('leader-game');
  const podium = document.getElementById('leader-podium'), list = document.getElementById('leader-list'), meWrap = document.getElementById('leader-me-wrap'), meEl = document.getElementById('leader-me');
  const empty = document.getElementById('leader-empty'), count = document.getElementById('leader-count'), periodLabel = document.getElementById('leader-period-label');
  let state = JSON.parse(document.getElementById('leaderboard-initial').textContent);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function row(p, pinned=false){ return `<div class="leader-row ${p.me?'is-me':''} ${pinned?'pinned':''}"><span class="rank">${p.rank ? String(p.rank).padStart(2,'0') : '—'}</span><div class="player-avatar">${esc(p.avatar)}</div><div class="player-meta"><strong>${esc(p.username)}</strong><span>${esc(p.detail||'CREW player')}</span></div>${p.me?'<span class="you-pill">YOU</span>':''}<strong class="score">${p.points} <small>PTS</small></strong></div>`; }
  function render(){
    periodLabel.textContent = String(state.period_label||'').toUpperCase(); count.textContent = `${state.total_ranked} ranked`;
    empty.hidden = state.players.length>0; list.innerHTML = state.players.map(p=>row(p)).join('');
    meWrap.hidden = !state.me; meEl.innerHTML = state.me ? row(state.me,true) : '';
    const top = state.top || [];
    if (!top.length) podium.innerHTML = '<article class="glass-card podium-empty">No scores yet.</article>';
    else podium.innerHTML = top.map((p,i)=>`<article class="glass-card podium-card place-${i+1}"><span class="podium-rank">#${i+1}</span><div class="podium-avatar">${esc(p.avatar)}</div><strong>${esc(p.username)}</strong><span>${p.points} PTS</span><small>${esc(p.detail||'')}</small></article>`).join('');
  }
  async function load(){
    const params = new URLSearchParams({period:period.value, game:game.value});
    const response = await fetch(`${root.dataset.apiUrl}?${params}`, {headers:{'Accept':'application/json'}});
    if (!response.ok) return; state = await response.json(); history.replaceState(null,'',`/leaderboard?${params}`); render();
  }
  period.addEventListener('change',load); game.addEventListener('change',load); render();
})();

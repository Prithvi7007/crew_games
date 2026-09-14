(() => {
  const root = document.querySelector('[data-leaderboard]'); if (!root) return;
  const period = document.getElementById('leader-period'), game = document.getElementById('leader-game');
  const podium = document.getElementById('leader-podium'), list = document.getElementById('leader-list'), meWrap = document.getElementById('leader-me-wrap'), meEl = document.getElementById('leader-me');
  const empty = document.getElementById('leader-empty'), count = document.getElementById('leader-count'), periodLabel = document.getElementById('leader-period-label');
  let state = JSON.parse(document.getElementById('leaderboard-initial').textContent);

  function row(player, pinned=false){
    const wrapper=document.createElement('div'); wrapper.className=`leader-row ${player.me?'is-me':''} ${pinned?'pinned':''}`.trim();
    const rank=document.createElement('span'); rank.className='rank'; rank.textContent=player.rank ? String(player.rank).padStart(2,'0') : '—';
    const avatar=document.createElement('div'); avatar.className='player-avatar'; avatar.textContent=String(player.avatar ?? '');
    const meta=document.createElement('div'); meta.className='player-meta'; const name=document.createElement('strong'); name.textContent=String(player.username ?? ''); const detail=document.createElement('span'); detail.textContent=String(player.detail || 'CREW player'); meta.append(name,detail);
    wrapper.append(rank,avatar,meta);
    if(player.me){const you=document.createElement('span');you.className='you-pill';you.textContent='YOU';wrapper.append(you);}
    const score=document.createElement('strong');score.className='score';score.append(document.createTextNode(String(player.points)),document.createTextNode(' '));const small=document.createElement('small');small.textContent='PTS';score.append(small);wrapper.append(score);
    return wrapper;
  }
  function podiumCard(player,index){
    const card=document.createElement('article');card.className=`glass-card podium-card place-${index+1}`;
    const rank=document.createElement('span');rank.className='podium-rank';rank.textContent=`#${index+1}`;
    const avatar=document.createElement('div');avatar.className='podium-avatar';avatar.textContent=String(player.avatar ?? '');
    const name=document.createElement('strong');name.textContent=String(player.username ?? '');
    const score=document.createElement('span');score.textContent=`${player.points} PTS`;
    const detail=document.createElement('small');detail.textContent=String(player.detail || '');
    card.append(rank,avatar,name,score,detail);return card;
  }
  function render(){
    periodLabel.textContent = String(state.period_label||'').toUpperCase(); count.textContent = `${state.total_ranked} ranked`;
    empty.hidden = state.players.length>0; list.replaceChildren(...state.players.map(p=>row(p)));
    meWrap.hidden = !state.me; meEl.replaceChildren(...(state.me ? [row(state.me,true)] : []));
    const top = state.top || [];
    if (!top.length){const card=document.createElement('article');card.className='glass-card podium-empty';card.textContent='No scores yet.';podium.replaceChildren(card);}
    else podium.replaceChildren(...top.map((p,i)=>podiumCard(p,i)));
  }
  async function load(){
    const params = new URLSearchParams({period:period.value, game:game.value});
    const response = await fetch(`${root.dataset.apiUrl}?${params}`, {headers:{'Accept':'application/json'}});
    if (!response.ok) return; state = await response.json(); history.replaceState(null,'',`/leaderboard?${params}`); render();
  }
  period.addEventListener('change',load); game.addEventListener('change',load); render();
})();

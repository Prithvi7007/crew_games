(() => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const root = document.querySelector('[data-mystery]'); if (!root) return;
  let state = JSON.parse(document.getElementById('mystery-state').textContent);
  const clues = document.getElementById('clue-list'), points = document.getElementById('mystery-points'), count = document.getElementById('clue-count');
  const form = document.getElementById('mystery-form'), input = document.getElementById('mystery-answer'), reveal = document.getElementById('reveal-clue'), message = document.getElementById('mystery-message');

  function renderClues() {
    clues.replaceChildren(...state.clues.map((clue, index) => {
      const article = document.createElement('article'); article.className = 'clue-card';
      const number = document.createElement('span'); number.textContent = String(index + 1).padStart(2, '0');
      const text = document.createElement('p'); text.textContent = String(clue ?? '');
      article.append(number, text);
      return article;
    }));
  }

  function render(){
    renderClues();
    points.textContent = state.completed ? state.score : state.potential_score;
    count.textContent = `Clue ${state.revealed_count} of ${state.total_clues}`;
    const done = state.completed; const locked = done || !state.playable;
    input.disabled = locked; form.querySelector('button').disabled = locked; reveal.disabled = locked || state.revealed_count >= state.total_clues;
    if(!state.playable && !done){ message.className='game-message neutral'; message.textContent='This challenge has not opened yet.'; }
    else if(done){ message.className='game-message success'; message.textContent = state.won ? `Solved: ${state.answer} · ${state.score} points` : `Answer: ${state.answer} · ${state.score} participation points`; }
  }
  async function post(url, body){ const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':csrfToken},body:body?JSON.stringify(body):null}); const d=await r.json(); if(!r.ok) throw new Error(d.message||'Try again.'); return d; }
  form.addEventListener('submit', async e=>{e.preventDefault(); if(!input.value.trim()) return; message.textContent='Checking…'; try{ const d=await post(root.dataset.guessUrl,{answer:input.value}); state=d.state; input.value=''; message.className=`game-message ${d.correct?'success':'error'}`; message.textContent=d.message; render(); }catch(err){message.className='game-message error';message.textContent=err.message;} });
  reveal.addEventListener('click', async()=>{try{const d=await post(root.dataset.revealUrl);state=d.state;message.textContent='Another clue unlocked.';render();}catch(err){message.className='game-message error';message.textContent=err.message;}});
  render();
})();

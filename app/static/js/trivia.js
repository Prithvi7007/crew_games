(() => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const root=document.querySelector('[data-trivia]'); if(!root) return;
  let state=JSON.parse(document.getElementById('trivia-state').textContent), pending=null;
  const q=document.getElementById('trivia-question'), opts=document.getElementById('trivia-options'), feedback=document.getElementById('trivia-feedback'), next=document.getElementById('trivia-next'), score=document.getElementById('trivia-score'), label=document.getElementById('trivia-progress-label'), bar=document.getElementById('trivia-progress-bar'), result=document.getElementById('trivia-result');

  function renderOptions() {
    opts.replaceChildren(...state.question.options.map((option, index) => {
      const button = document.createElement('button'); button.type = 'button'; button.dataset.answer = String(index);
      const marker = document.createElement('span'); marker.textContent = String.fromCharCode(65 + index);
      button.append(marker, document.createTextNode(String(option ?? '')));
      return button;
    }));
  }

  function renderResult() {
    result.replaceChildren(); result.hidden = false;
    const strong = document.createElement('strong'); strong.textContent = String(state.score);
    const pointsLabel = document.createElement('span'); pointsLabel.textContent = 'POINTS';
    const copy = document.createElement('p'); copy.textContent = `${state.correct_count} of ${state.total} correct`;
    const link = document.createElement('a'); link.className = 'secondary-button'; link.href = root.dataset.returnUrl || '/home'; link.textContent = `Back to ${state.archive ? 'game archive' : 'CREW home'}`;
    result.append(strong, pointsLabel, copy, link);
  }

  function render(){
    score.textContent=state.correct_count*10;
    if(!state.playable && !state.completed){ q.textContent='This challenge has not opened yet.'; opts.replaceChildren(); label.textContent='Coming soon'; bar.style.width='0%'; next.hidden=true; return; }
    bar.style.width=`${state.index/state.total*100}%`;
    if(state.completed){ q.textContent='Round complete.'; opts.replaceChildren(); label.textContent=`${state.total} of ${state.total} answered`; renderResult(); return; }
    result.hidden = true;
    label.textContent=`Question ${state.index+1} of ${state.total}`; q.textContent=state.question.prompt; renderOptions(); feedback.textContent=''; feedback.className='game-message'; next.hidden=true; pending=null;
  }
  async function answer(index){ if(pending!==null)return; pending=index; opts.querySelectorAll('button').forEach(b=>b.disabled=true); const r=await fetch(root.dataset.answerUrl,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':csrfToken},body:JSON.stringify({selected:index})}); const d=await r.json(); if(!r.ok){feedback.className='game-message error';feedback.textContent=d.message||'Try again.';pending=null;return;} const buttons=opts.querySelectorAll('button'); buttons[d.correct_index]?.classList.add('correct'); if(!d.correct) buttons[index]?.classList.add('wrong'); feedback.className=`game-message ${d.correct?'success':'error'}`; feedback.textContent=d.correct?'Correct.':`Not quite — ${d.correct_answer}.`; state=d.state; score.textContent=state.correct_count*10; if(state.completed){setTimeout(render,700);} else {next.hidden=false;} }
  opts.addEventListener('click',e=>{const b=e.target.closest('[data-answer]');if(b)answer(Number(b.dataset.answer));}); next.addEventListener('click',render); render();
})();

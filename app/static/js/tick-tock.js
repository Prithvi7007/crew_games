(() => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const root=document.querySelector('[data-timer]'); if(!root) return;
  let state=JSON.parse(document.getElementById('timer-state').textContent), running=state.started&&!state.completed, busy=false;
  const action=document.getElementById('timer-action'), display=document.getElementById('timer-countdown'), message=document.getElementById('timer-message'), result=document.getElementById('timer-result');
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  function showResult(){ result.hidden=false; result.innerHTML=`<div><strong>${Number(state.elapsed).toFixed(2)}</strong><span>YOUR TIME</span></div><div><strong>${Number(state.difference).toFixed(2)}</strong><span>OFF TARGET</span></div><div><strong>${state.score}</strong><span>POINTS</span></div>`; display.textContent='STOP'; action.disabled=true; action.textContent='Round complete'; message.className='game-message success'; message.textContent=`Target ${state.target.toFixed(2)} sec · You stopped at ${Number(state.elapsed).toFixed(2)} sec.`; }
  async function request(url){const r=await fetch(url,{method:'POST',headers:{'Accept':'application/json','X-CSRFToken':csrfToken}});const d=await r.json();if(!r.ok)throw new Error(d.message||'Try again.');return d;}
  async function begin(){if(busy||running)return;busy=true;action.disabled=true;for(const t of ['3','2','1']){display.textContent=t;await sleep(650);} try{const d=await request(root.dataset.startUrl);state=d.state;running=true;display.textContent='GO';message.textContent='The timer is hidden. Stop when your internal clock says it is time.';action.textContent='STOP';action.disabled=false;}catch(e){message.className='game-message error';message.textContent=e.message;}busy=false;}
  async function stop(){if(busy||!running)return;busy=true;action.disabled=true;try{const d=await request(root.dataset.stopUrl);state=d.state;running=false;showResult();}catch(e){message.className='game-message error';message.textContent=e.message;action.disabled=false;}busy=false;}
  action.addEventListener('click',()=>running?stop():begin()); document.addEventListener('keydown',e=>{if(e.code==='Space'&&running){e.preventDefault();stop();}});
  if(state.completed) showResult(); else if(running){display.textContent='GO';action.textContent='STOP';message.textContent='The hidden timer is still running.';}
})();

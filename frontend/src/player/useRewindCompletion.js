import {useCallback, useRef} from 'react';

// Completion is optional: failure or an interrupted network must not trap gameplay.
export default function useRewindCompletion(url) {
  const saved=useRef(false);
  const pending=useRef(null);
  return useCallback(action=>{
    if(!url||saved.current)return Promise.resolve();
    if(pending.current)return pending.current;
    const controller=new AbortController();
    const deadline=window.setTimeout(()=>controller.abort(),2500);
    pending.current=fetch(url,{
      method:'POST',credentials:'same-origin',keepalive:true,signal:controller.signal,
      headers:{'Content-Type':'application/json',
        'X-CSRFToken':document.querySelector('meta[name="csrf-token"]')?.content||''},
      body:JSON.stringify({action}),
    }).then(response=>{if(response.ok)saved.current=true;})
      .catch(()=>{})
      .finally(()=>{window.clearTimeout(deadline);pending.current=null;});
    return pending.current;
  },[url]);
}

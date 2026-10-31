/** Explicit start, pause and completion states keep the cover and finale honest. */
export function initialPlayback() {
  return {index:0, started:false, playing:false, finished:false};
}

export function remainingChapterTime(duration, elapsed) {
  return Math.max(0,duration-elapsed);
}

export function playbackReducer(state, action) {
  switch (action.type) {
    case 'begin':
      return {...state, started:true, playing:!action.reduced, finished:false};
    case 'toggle':
      return state.started&&!state.finished ? {...state, playing:!state.playing} : state;
    case 'pause':
      return state.playing ? {...state, playing:false} : state;
    case 'go': {
      if(!state.started||action.count<1)return state;
      const index=Math.max(0,Math.min(action.count-1,action.index));
      return {...state,index,finished:index===action.count-1&&!state.playing};
    }
    case 'finish':
      return state.finished&&!state.playing ? state : {...state,playing:false,finished:true};
    case 'restart':
      return initialPlayback();
    default:
      return state;
  }
}

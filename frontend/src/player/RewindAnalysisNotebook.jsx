import React from 'react';

/* Read-only, staff-gated analytical proof before cinematic treatment.
 * Everything shown is calculated from the same cutoff-filtered season rows.
 */
export default function RewindAnalysisNotebook({data}) {
  const recap=data.rewind || {};
  const story=recap.analyticsStory || {cards:[],sample:{},limitations:''};
  const cards=story.cards || [];
  const subject=data.rewindPreviewPlayer || recap.username || 'this player';
  const back='/rewind?preview=1&prototype=1'+
    (data.rewindPreviewPlayer ? '&player='+encodeURIComponent(data.rewindPreviewPlayer) : '');
  const [copyStatus,setCopyStatus]=React.useState('');

  async function copyFindings() {
    const reportText=[
      'CREW Season 01 — analytical evidence for '+subject,
      'Completed games: '+(story.sample?.completedGames ?? 0)+
        '; weeks active: '+(story.sample?.weeksActive ?? 0)+
        '; other active players: '+(story.sample?.otherActivePlayers ?? 0),
      ...cards.map((card,i)=>[
        String(i+1)+'. '+card.title+' — '+card.metric,
        card.story, 'Evidence: '+card.evidence, 'Method: '+card.method,
      ].join('\n')),
      'Limitations: '+story.limitations,
    ].join('\n\n');
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(reportText);
      setCopyStatus('Research findings copied.');
    } catch (_) {
      setCopyStatus('Copy is unavailable in this browser.');
    }
  }

  return <main className="rewind-analysis" aria-label="Private CREW Rewind analytics review">
    <header className="rewind-analysis-header">
      <span className="rewind-analysis-logo">CREW<span>+</span> <small>REWIND / RESEARCH</small></span>
      <a href={back}>Return to Film Lab <span aria-hidden="true">↗</span></a>
    </header>
    <div className="rewind-analysis-content">
      <p className="rewind-analysis-kicker">SEASON 01 / EVIDENCE BEFORE ANIMATION / PRIVATE STAFF PREVIEW</p>
      <h1>What did <em>{subject}</em> actually reveal?</h1>
      <p className="rewind-analysis-deck">
        Not a leaderboard, not a collection of game totals. Each discovery
        tests a question against the real completed-game records.
        Claims without a sufficient comparison group are omitted.
      </p>
      <div className="rewind-analysis-sample">
        <span><strong>{story.sample?.completedGames ?? 0}</strong> completed games</span>
        <span><strong>{story.sample?.weeksActive ?? 0}</strong> active weeks</span>
        <span><strong>{story.sample?.otherActivePlayers ?? 0}</strong> other active players</span>
      </div>
      <button className="rewind-analysis-copy" type="button" onClick={copyFindings}>
        Copy the evidence report <span aria-hidden="true">↗</span>
      </button>
      {copyStatus && <p className="rewind-analysis-copy-status" role="status">{copyStatus}</p>}
      {cards.length ? <div className="rewind-analysis-findings">
        {cards.map((finding,i)=><article className="rewind-analysis-finding" key={finding.key}>
          <div className="rewind-analysis-finding-index">{String(i+1).padStart(2,'0')} <span>{finding.label}</span></div>
          <div className="rewind-analysis-finding-main">
            <h2>{finding.title}</h2>
            <p className="rewind-analysis-finding-story">{finding.story}</p>
            <p className="rewind-analysis-evidence">{finding.evidence}</p>
            <details className="rewind-analysis-method">
              <summary>How we know this</summary>
              <p>{finding.method}</p>
            </details>
          </div>
          <strong className="rewind-analysis-finding-number">{finding.metric}</strong>
        </article>)}
      </div> : <section className="rewind-analysis-empty">
        <h2>No defensible comparisons yet.</h2>
        <p>There are too few eligible completions or peer observations to tell a
        reliable analytical story for this player. We won't fill the gaps with
        generic personality labels.</p>
      </section>}
      <footer className="rewind-analysis-footer">
        <p><strong>Interpretation notes.</strong> {story.limitations}</p>
        <p>This research preview is visible only to CREW staff. No rankings, scores,
          awards, or championship data have been changed.</p>
        <a href={back}>Back to the current film <span aria-hidden="true">→</span></a>
      </footer>
    </div>
  </main>;
}

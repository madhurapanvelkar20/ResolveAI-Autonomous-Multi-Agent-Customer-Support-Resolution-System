import React, { useState } from 'react';
import { TraceEvent } from '../types';

interface TraceTimelineProps {
  events: TraceEvent[];
}

export const TraceTimeline: React.FC<TraceTimelineProps> = ({ events }) => {
  const [filterAgent, setFilterAgent] = useState<string>('all');
  const [showDetails, setShowDetails] = useState<boolean>(false);

  if (!events || events.length === 0) {
    return (
      <div className="card timeline-card empty-state">
        <h3>Execution Trace Timeline</h3>
        <p>No trace events recorded for this case yet.</p>
      </div>
    );
  }

  const filtered = events.filter((ev) => {
    if (filterAgent === 'all') return true;
    return (ev.agent || 'runtime').toLowerCase() === filterAgent.toLowerCase();
  });

  return (
    <div className="card timeline-card">
      <div className="timeline-header">
        <div>
          <h2>Execution Trace Timeline ({events.length} Events)</h2>
          <p className="subtitle">Immutable thread-safe runtime events captured by TraceLogger.</p>
        </div>
        <div className="timeline-controls">
          <label htmlFor="agent-filter">Filter by Actor:</label>
          <select
            id="agent-filter"
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
          >
            <option value="all">All Actors</option>
            <option value="triage">Triage</option>
            <option value="investigation">Investigation</option>
            <option value="resolution">Resolution</option>
            <option value="critic">Critic</option>
            <option value="runtime">Runtime/System</option>
          </select>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => setShowDetails(!showDetails)}
          >
            {showDetails ? 'Hide JSON Details' : 'Show JSON Details'}
          </button>
        </div>
      </div>

      <div className="timeline-list">
        {filtered.map((ev) => {
          const actor = ev.agent || 'runtime';
          const title = `${ev.event} (${actor})`;
          const details = ev.reason_summary || ev.message || ev.tool_result_summary || '';

          return (
            <div key={ev.seq} className="timeline-entry">
              <div className="entry-seq">#{ev.seq}</div>
              <div className="entry-marker"></div>
              <div className="entry-body">
                <div className="entry-header">
                  <span className="entry-title">{title}</span>
                  <span className="entry-iter">Iter: {ev.iteration}</span>
                  <span className="entry-time">{new Date(ev.ts).toLocaleTimeString()}</span>
                </div>
                {details && <p className="entry-detail">{details}</p>}
                {ev.tool && (
                  <p className="entry-tool">
                    <strong>Tool:</strong> <code>{ev.tool}</code>
                  </p>
                )}
                {showDetails && (
                  <pre className="entry-raw">{JSON.stringify(ev, null, 2)}</pre>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

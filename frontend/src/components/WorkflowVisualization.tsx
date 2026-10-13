import React from 'react';
import { CaseResult, TraceEvent } from '../types';

interface WorkflowVisualizationProps {
  caseId: string | null;
  result: CaseResult | null;
  traceEvents: TraceEvent[];
  isLoading: boolean;
  error: string | null;
}

export const WorkflowVisualization: React.FC<WorkflowVisualizationProps> = ({
  caseId,
  result,
  traceEvents,
  isLoading,
  error,
}) => {
  if (isLoading) {
    return (
      <div className="card result-card loading-state">
        <div className="spinner"></div>
        <h3>Orchestrating Multi-Agent Workflow...</h3>
        <p>Triage, Investigation, Resolution, and Critic agents are interacting.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card result-card error-state">
        <div className="status-banner banner-failed">
          <h3>Workflow Error</h3>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!result && !caseId) {
    return (
      <div className="card result-card empty-state">
        <h3>Workflow Results</h3>
        <p>No active case execution. Submit a case or select a demo scenario to view results.</p>
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'resolved':
        return <span className="badge badge-success">RESOLVED</span>;
      case 'escalated':
        return <span className="badge badge-warning">ESCALATED</span>;
      case 'failed':
        return <span className="badge badge-danger">FAILED</span>;
      default:
        return <span className="badge badge-info">{status.toUpperCase()}</span>;
    }
  };

  // Extract agent decisions and tools from trace events
  const agentDecisions = traceEvents.filter((e) => e.event === 'agent_decision');
  const toolCalls = traceEvents.filter((e) => e.event === 'tool_call' || e.event === 'tool_result');
  const policyReferences = traceEvents
    .filter((e) => e.input_refs && e.input_refs.length > 0)
    .flatMap((e) => e.input_refs || []);

  const triageEvent = agentDecisions.find((e) => e.agent === 'triage');
  const investigationEvent = agentDecisions.find((e) => e.agent === 'investigation');
  const resolutionEvent = agentDecisions.find((e) => e.agent === 'resolution');
  const criticEvent = agentDecisions.find((e) => e.agent === 'critic');

  return (
    <div className="card result-card">
      <div className="result-header">
        <div>
          <h2>Case Execution: {caseId || result?.case_id}</h2>
          <span className="trace-tag">Trace ID: {result?.trace_id || 'N/A'}</span>
        </div>
        <div>{result && getStatusBadge(result.status)}</div>
      </div>

      {result && (
        <div className="summary-banner">
          <h4>Customer Facing Response:</h4>
          <p className="response-text">{result.customer_response}</p>
          {result.escalation_reason && (
            <div className="alert alert-warning">
              <strong>Escalation Reason:</strong> {result.escalation_reason}
            </div>
          )}
          {result.resolution && (
            <div className="alert alert-success">
              <strong>Approved Resolution:</strong> {result.resolution.type}
              {result.resolution.amount && ` — $${result.resolution.amount} ${result.resolution.currency || 'USD'}`}
            </div>
          )}
        </div>
      )}

      <div className="agent-pipeline">
        <h3>Autonomous Multi-Agent Activity</h3>

        {/* Triage Step */}
        <div className={`pipeline-step ${triageEvent ? 'step-active' : ''}`}>
          <div className="step-title">
            <span className="agent-badge triage-badge">Triage Agent</span>
            <span>{triageEvent ? `Decision: ${triageEvent.decision}` : 'Awaiting Triage'}</span>
          </div>
          {triageEvent && (
            <div className="step-content">
              <p><strong>Reasoning:</strong> {triageEvent.reason_summary}</p>
              {triageEvent.confidence !== null && triageEvent.confidence !== undefined && (
                <small>Confidence: {(triageEvent.confidence * 100).toFixed(0)}%</small>
              )}
            </div>
          )}
        </div>

        {/* Investigation Step */}
        <div className={`pipeline-step ${investigationEvent || toolCalls.length > 0 ? 'step-active' : ''}`}>
          <div className="step-title">
            <span className="agent-badge investigation-badge">Investigation Agent</span>
            <span>{investigationEvent ? `Decision: ${investigationEvent.decision}` : 'No Investigation Required'}</span>
          </div>
          {investigationEvent && (
            <div className="step-content">
              <p><strong>Findings:</strong> {investigationEvent.reason_summary}</p>
            </div>
          )}
          {toolCalls.length > 0 && (
            <div className="tool-calls-block">
              <h5>Verified Tool Activity ({toolCalls.length} events):</h5>
              <ul>
                {toolCalls.map((tc, idx) => (
                  <li key={idx}>
                    <code>{tc.tool || 'system'}</code>: {tc.tool_result_summary || tc.event}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Resolution Step */}
        <div className={`pipeline-step ${resolutionEvent ? 'step-active' : ''}`}>
          <div className="step-title">
            <span className="agent-badge resolution-badge">Resolution Agent</span>
            <span>{resolutionEvent ? `Proposal: ${resolutionEvent.decision}` : 'Pending Proposal'}</span>
          </div>
          {resolutionEvent && (
            <div className="step-content">
              <p><strong>Rationale:</strong> {resolutionEvent.reason_summary}</p>
            </div>
          )}
        </div>

        {/* Critic Step */}
        <div className={`pipeline-step ${criticEvent ? 'step-active' : ''}`}>
          <div className="step-title">
            <span className="agent-badge critic-badge">Adversarial Critic</span>
            <span>
              {result?.critic_decision
                ? `Audit: ${result.critic_decision.toUpperCase()}`
                : criticEvent
                ? `Audit: ${criticEvent.decision?.toUpperCase()}`
                : 'Not Audited'}
            </span>
          </div>
          {criticEvent && (
            <div className="step-content">
              <p><strong>Audit Finding:</strong> {criticEvent.reason_summary}</p>
            </div>
          )}
        </div>
      </div>

      {policyReferences.length > 0 && (
        <div className="policy-evidence-section">
          <h4>Policy Evidence &amp; Citations:</h4>
          <ul>
            {policyReferences.map((ref, i) => (
              <li key={i} className="citation-item">
                <code>{ref}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="metrics-bar">
        <span><strong>Iterations:</strong> {result?.iterations ?? 0}</span>
        <span><strong>Tools Used:</strong> {result?.tools_used.join(', ') || 'None'}</span>
        <span><strong>Confidence:</strong> {result ? `${(result.confidence * 100).toFixed(0)}%` : 'N/A'}</span>
      </div>
    </div>
  );
};

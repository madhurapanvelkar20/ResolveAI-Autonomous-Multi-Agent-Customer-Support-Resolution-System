import React from 'react';
import { CaseResult, CustomerTimelineEvent, CustomerTimelineStage, FinancialActionStatus } from '../types';

interface WorkflowVisualizationProps {
  caseId: string | null;
  result: CaseResult | null;
  isLoading: boolean;
  error: string | null;
  isMock?: boolean;
}

const MockModeIndicator = () => (
  <span className="mode-badge-mock">Deterministic Mock Mode</span>
);

function formatAmount(amount: number | string | null | undefined, currency?: string | null) {
  if (amount === null || amount === undefined || amount === '') return '';
  return currency === 'USD' || !currency ? ` $${amount}` : ` ${currency} ${amount}`;
}

const stageTitles: Record<CustomerTimelineStage, string> = {
  case_received: 'Complaint received',
  payment_verification: 'Payment verification',
  order_verification: 'Order verification',
  policy_review: 'Policy review',
  evidence_check: 'Evidence and information check',
  safety_check: 'Risk and safety review',
  resolution_decision: 'Resolution decision',
  next_steps: 'Next steps',
};

const outcomeLabels: Record<string, string> = {
  received: 'Received',
  verified: 'Verified',
  not_found: 'Not found',
  unable_to_verify: 'Could not verify',
  guidance_found: 'Guidance found',
  guidance_not_found: 'No matching guidance',
  unavailable: 'Unavailable',
  needs_information: 'More information needed',
  passed: 'Passed',
  not_approved: 'Not approved',
  needs_review: 'Review needed',
  proposed: 'Proposed',
  approved: 'Approved',
  rejected: 'Rejected',
  waiting_for_information: 'Waiting for information',
  specialist_review: 'Specialist review',
  resolved: 'Resolved',
  contact_support: 'Contact support',
};

function resolvedFinancialStatus(result: CaseResult): FinancialActionStatus | null {
  if (result.financial_action_status) return result.financial_action_status;
  if (result.resolution?.type.toLowerCase() !== 'refund') return null;
  if (result.status === 'resolved' && result.critic_decision === 'approve') return 'approved';
  if (result.critic_decision === 'reject') return 'rejected';
  return 'proposed';
}

function refundMessage(
  status: FinancialActionStatus,
  result: CaseResult,
): string {
  const amount = formatAmount(result.resolution?.amount, result.resolution?.currency);
  switch (status) {
    case 'approved':
      return `Your refund${amount} was approved. The backend has not confirmed that it was submitted or completed.`;
    case 'submitted':
      return `Your refund${amount} was submitted.`;
    case 'completed':
      return `Your refund${amount} was completed.`;
    case 'rejected':
      return 'The proposed refund was not approved. A support specialist will review the case.';
    default:
      return `A refund${amount} was proposed, but it has not been approved.`;
  }
}

function fallbackTimeline(
  result: CaseResult | null,
  caseId: string | null,
  financialStatus: FinancialActionStatus | null,
): CustomerTimelineEvent[] {
  const events: CustomerTimelineEvent[] = [];
  if (caseId || result) events.push({ stage: 'case_received', outcome: 'received' });
  if (financialStatus) {
    events.push({
      stage: 'resolution_decision',
      outcome: financialStatus,
    });
  } else if (result?.status === 'resolved') {
    events.push({
      stage: 'resolution_decision',
      outcome: 'approved',
      explanation: result.customer_summary || 'The proposed resolution was approved.',
    });
  }
  if (result?.status === 'escalated') {
    const waiting = result.customer_timeline?.some(
      (event) => event.outcome === 'waiting_for_information'
    );
    events.push({
      stage: 'next_steps',
      outcome: waiting ? 'waiting_for_information' : 'specialist_review',
      explanation: result.customer_summary || 'A support specialist needs to review this case.',
    });
  } else if (result?.status === 'failed') {
    events.push({
      stage: 'next_steps',
      outcome: 'contact_support',
      explanation: result.customer_summary || 'Please contact support for help completing this case.',
    });
  }
  return events;
}

export const WorkflowVisualization: React.FC<WorkflowVisualizationProps> = ({
  caseId,
  result,
  isLoading,
  error,
  isMock,
}) => {
  const mockIndicator = isMock && (caseId || result || isLoading || error)
    ? <MockModeIndicator />
    : null;

  if (isLoading) {
    return (
      <div className="card result-card loading-state">
        {mockIndicator}
        <div className="spinner"></div>
        <h3>Reviewing your case</h3>
        <p>Checking the information provided and the relevant support policies.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card result-card error-state">
        {mockIndicator}
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

  const financialStatus = result ? resolvedFinancialStatus(result) : null;
  const waitingForInformation = result?.customer_timeline?.some(
    (event) => event.outcome === 'waiting_for_information'
  );
  const statusLabel = financialStatus === 'approved'
    ? 'REFUND APPROVED'
    : financialStatus === 'proposed'
    ? 'REFUND PROPOSED'
    : financialStatus === 'rejected'
    ? 'REFUND NOT APPROVED'
    : financialStatus === 'submitted'
    ? 'REFUND SUBMITTED'
    : financialStatus === 'completed'
    ? 'REFUND COMPLETED'
    : result?.status === 'resolved'
    ? 'RESOLVED'
    : result?.status === 'escalated'
    ? waitingForInformation
      ? 'WAITING FOR INFORMATION'
      : 'SPECIALIST REVIEW'
    : 'REVIEW INCOMPLETE';
  const statusClass = financialStatus === 'approved' || financialStatus === 'completed' || result?.status === 'resolved'
    ? 'badge-success'
    : result?.status === 'escalated' || financialStatus === 'proposed' || financialStatus === 'submitted'
    ? 'badge-warning'
    : 'badge-danger';
  const customerSummary = result
    ? result.customer_summary || (financialStatus
      ? refundMessage(financialStatus, result)
      : result.status === 'escalated'
        ? 'A support specialist needs to review this case before a decision can be made.'
        : result.status === 'failed'
        ? 'The automated review could not be completed. Please contact support.'
        : result.customer_response)
    : null;
  const financialMessage = result && financialStatus && result.customer_summary
    ? refundMessage(financialStatus, result)
    : null;
  const events = result?.customer_timeline?.length
    ? result.customer_timeline
    : fallbackTimeline(result, caseId, financialStatus);

  return (
    <div className="card result-card">
      <div className="result-header">
        <div>
          <h2>Case update</h2>
          {(caseId || result) && (
            <p className="case-reference">Case reference: {caseId || result?.case_id}</p>
          )}
          {mockIndicator}
        </div>
        <div>{result && <span className={`badge ${statusClass}`}>{statusLabel}</span>}</div>
      </div>

      {result && (
        <div className="summary-banner">
          <p className="response-text">{customerSummary}</p>
          {financialMessage && <p className="financial-status-detail">{financialMessage}</p>}
        </div>
      )}

      <div className="customer-timeline" aria-label="Case timeline">
        <h3>Case timeline</h3>
        <ol>
          {events.map((event, index) => (
            <li key={`${event.stage}-${index}`}>
              <span className="customer-timeline-marker" aria-hidden="true" />
              <div>
                <div className="customer-timeline-heading">
                  <strong>{stageTitles[event.stage]}</strong>
                  <span className="timeline-outcome">
                    {outcomeLabels[event.outcome] || event.outcome}
                  </span>
                </div>
                {event.explanation && <p>{event.explanation}</p>}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
};

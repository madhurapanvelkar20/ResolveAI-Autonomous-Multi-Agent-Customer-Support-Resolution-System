import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WorkflowVisualization } from '../components/WorkflowVisualization';
import { CaseResult } from '../types';

describe('WorkflowVisualization Component', () => {
  it('renders customer-friendly loading state without internal agent names', () => {
    render(
      <WorkflowVisualization
        caseId="case-1"
        result={null}
        isLoading={true}
        error={null}
        isMock={true}
      />
    );
    expect(screen.getByText('Reviewing your case')).toBeInTheDocument();
    expect(screen.getByText('Deterministic Mock Mode')).toBeInTheDocument();
    expect(screen.queryByText(/Triage Agent|Investigation Agent|Resolution Agent|Critic Agent/i)).not.toBeInTheDocument();
  });

  it('renders error state when error is provided', () => {
    render(
      <WorkflowVisualization
        caseId="case-1"
        result={null}
        isLoading={false}
        error="Network error connecting to API"
      />
    );
    expect(screen.getByText(/Workflow Error/i)).toBeInTheDocument();
    expect(screen.getByText(/Network error connecting to API/i)).toBeInTheDocument();
  });

  it('renders empty state when no case or result exists', () => {
    render(
      <WorkflowVisualization
        caseId={null}
        result={null}
        isLoading={false}
        error={null}
      />
    );
    expect(screen.getByText(/No active case execution/i)).toBeInTheDocument();
  });

  it('shows an approved refund without claiming it was submitted or completed', () => {
    const mockResult: CaseResult = {
      case_id: 'case-demo-1',
      status: 'resolved',
      customer_response: 'Your refund has been completed.',
      resolution: { type: 'refund', amount: 49.99, currency: 'USD' },
      confidence: 0.98,
      agents_involved: ['triage', 'investigation', 'resolution', 'critic'],
      tools_used: ['lookup_payment'],
      iterations: 4,
      critic_decision: 'approve',
      trace_id: 'trace-test-123',
      customer_summary: 'The refund was approved after a matching payment record was verified and policy guidance was retrieved.',
      customer_timeline: [
        { stage: 'case_received', outcome: 'received' },
        { stage: 'payment_verification', outcome: 'verified', explanation: 'A matching payment record was found and checked.' },
        { stage: 'policy_review', outcome: 'guidance_found', explanation: 'Policy guidance was retrieved for review.' },
        { stage: 'safety_check', outcome: 'passed', explanation: 'The proposed resolution passed the automated safety review.' },
        { stage: 'resolution_decision', outcome: 'approved', explanation: 'The proposed resolution was approved.' },
        { stage: 'next_steps', outcome: 'resolved', explanation: 'The case has been marked resolved.' },
      ],
      financial_action_status: 'approved',
    };

    render(
      <WorkflowVisualization
        caseId="case-demo-1"
        result={mockResult}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByText('REFUND APPROVED')).toBeInTheDocument();
    expect(screen.getByText(/payment record was verified and policy guidance was retrieved/i)).toBeInTheDocument();
    expect(screen.getByText('Complaint received')).toBeInTheDocument();
    expect(screen.getByText('Payment verification')).toBeInTheDocument();
    expect(screen.getByText('Policy review')).toBeInTheDocument();
    expect(screen.getByText('Risk and safety review')).toBeInTheDocument();
    expect(screen.getByText('Resolution decision')).toBeInTheDocument();
    expect(screen.getByText('Next steps')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('Guidance found')).toBeInTheDocument();
    expect(screen.getByText('Passed')).toBeInTheDocument();
    expect(screen.getByText('Your refund $49.99 was approved. The backend has not confirmed that it was submitted or completed.')).toBeInTheDocument();
    expect(screen.queryByText(/Your refund has been completed/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Triage Agent|Investigation Agent|Resolution Agent|Critic Agent|lookup_payment|Trace ID/i)).not.toBeInTheDocument();
  });

  it.each([
    ['mock_skipped', 'Mock mode; no external workflow was called.'],
    ['not_configured', 'n8n is not configured; no external workflow was called.'],
    ['accepted', 'n8n accepted the safe workflow request; completion is not yet confirmed.'],
    ['completed', 'The safe n8n demonstration workflow completed.'],
    ['failed', 'The safe n8n workflow failed; completion was not confirmed.'],
    ['timed_out', 'The safe n8n workflow timed out; completion was not confirmed.'],
  ] as const)('shows safe integration status %s without exposing diagnostics', (status, message) => {
    const result: CaseResult = {
      case_id: 'case-integration',
      status: 'resolved',
      customer_response: 'A support resolution is ready.',
      resolution: { type: 'explanation' },
      confidence: 0.9,
      agents_involved: [],
      tools_used: [],
      iterations: 1,
      critic_decision: 'approve',
      trace_id: 'trace-internal',
      workflow_integration_status: status,
    };

    render(
      <WorkflowVisualization
        caseId={result.case_id}
        result={result}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByRole('status')).toHaveTextContent(message);
    expect(screen.queryByText(/trace-internal|webhook|token|payment_id/i)).not.toBeInTheDocument();
  });

  it('labels an unapproved refund as proposed and suppresses completion claims', () => {
    const mockResult: CaseResult = {
      case_id: 'case-demo-2',
      status: 'escalated',
      customer_response: 'Your refund has been completed.',
      resolution: { type: 'refund', amount: 49.99, currency: 'USD' },
      confidence: 0.75,
      agents_involved: ['resolution', 'critic'],
      tools_used: [],
      iterations: 2,
      critic_decision: 'request_evidence',
      escalation_reason: 'Internal review detail',
      trace_id: 'trace-test-456',
      customer_summary: 'More information is needed before a decision can be made.',
      customer_timeline: [
        { stage: 'case_received', outcome: 'received' },
        { stage: 'evidence_check', outcome: 'needs_information', explanation: 'More information is needed before a decision can be made.' },
        { stage: 'next_steps', outcome: 'waiting_for_information', explanation: 'The case is waiting for additional information.' },
      ],
      financial_action_status: 'proposed',
    };

    render(
      <WorkflowVisualization
        caseId="case-demo-2"
        result={mockResult}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByText('REFUND PROPOSED')).toBeInTheDocument();
    expect(screen.getByText(/A refund \$49\.99 was proposed, but it has not been approved/i)).toBeInTheDocument();
    expect(screen.getByText('Evidence and information check')).toBeInTheDocument();
    expect(screen.getByText('More information needed')).toBeInTheDocument();
    expect(screen.getByText('Waiting for information')).toBeInTheDocument();
    expect(screen.queryByText(/completed/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Internal review detail/i)).not.toBeInTheDocument();
  });

  it.each([
    ['submitted', 'REFUND SUBMITTED', 'Your refund $49.99 was submitted.'],
    ['completed', 'REFUND COMPLETED', 'Your refund $49.99 was completed.'],
  ] as const)('shows %s only when the backend explicitly reports it', (financial_action_status, label, message) => {
    const mockResult: CaseResult = {
      case_id: 'case-demo-financial',
      status: 'resolved',
      customer_response: 'Refund status update.',
      resolution: { type: 'refund', amount: 49.99, currency: 'USD' },
      confidence: 0.98,
      agents_involved: [],
      tools_used: [],
      iterations: 1,
      critic_decision: 'approve',
      trace_id: 'trace-test-financial',
      financial_action_status,
    };

    render(
      <WorkflowVisualization
        caseId={mockResult.case_id}
        result={mockResult}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it('explains a rejected refund without exposing internal escalation details', () => {
    const mockResult: CaseResult = {
      case_id: 'case-demo-rejected',
      status: 'escalated',
      customer_response: 'Internal status text',
      resolution: { type: 'refund', amount: 250, currency: 'USD' },
      confidence: 0.75,
      agents_involved: ['critic'],
      tools_used: [],
      iterations: 3,
      critic_decision: 'reject',
      escalation_reason: 'Sensitive review details',
      trace_id: 'trace-test-rejected',
      customer_summary: 'The proposed resolution was not approved. A support specialist will review the case before a final decision.',
      customer_timeline: [
        { stage: 'safety_check', outcome: 'not_approved', explanation: 'The proposed resolution did not pass the automated review.' },
        { stage: 'resolution_decision', outcome: 'rejected', explanation: 'The proposed resolution was not approved.' },
        { stage: 'next_steps', outcome: 'specialist_review', explanation: 'A support specialist will review the case.' },
      ],
      financial_action_status: 'rejected',
    };

    render(
      <WorkflowVisualization
        caseId={mockResult.case_id}
        result={mockResult}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByText('REFUND NOT APPROVED')).toBeInTheDocument();
    expect(screen.getAllByText(/proposed resolution was not approved/i).length).toBeGreaterThan(0);
    expect(screen.getByText('Specialist review')).toBeInTheDocument();
    expect(screen.queryByText(/Sensitive review details|Internal status text|critic|trace-test-rejected/i)).not.toBeInTheDocument();
  });

  it('uses customer-friendly escalation wording', () => {
    const mockResult: CaseResult = {
      case_id: 'case-demo-5',
      status: 'escalated',
      customer_response: 'Your case has been escalated to risk management.',
      confidence: 0.99,
      agents_involved: ['triage'],
      tools_used: [],
      iterations: 1,
      critic_decision: null,
      escalation_reason: 'High-risk fraud alert: chargeback threat exceeds safety limits.',
      trace_id: 'trace-test-789',
      customer_summary: 'This case needs specialist review before a decision can be made.',
      customer_timeline: [
        { stage: 'safety_check', outcome: 'needs_review', explanation: 'A specialist review is needed before this case can proceed.' },
        { stage: 'next_steps', outcome: 'specialist_review', explanation: 'A support specialist will review the case.' },
      ],
    };

    render(
      <WorkflowVisualization
        caseId="case-demo-5"
        result={mockResult}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByText('SPECIALIST REVIEW')).toBeInTheDocument();
    expect(screen.getByText(/needs specialist review before a decision can be made/i)).toBeInTheDocument();
    expect(screen.getByText('Risk and safety review')).toBeInTheDocument();
    expect(screen.queryByText(/High-risk fraud alert/i)).not.toBeInTheDocument();
  });
});

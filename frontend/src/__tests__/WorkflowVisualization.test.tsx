import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WorkflowVisualization } from '../components/WorkflowVisualization';
import { CaseResult, TraceEvent } from '../types';

describe('WorkflowVisualization Component', () => {
  it('renders loading state when isLoading is true', () => {
    render(
      <WorkflowVisualization
        caseId="case-1"
        result={null}
        traceEvents={[]}
        isLoading={true}
        error={null}
      />
    );
    expect(screen.getByText(/Orchestrating Multi-Agent Workflow/i)).toBeInTheDocument();
  });

  it('renders error state when error is provided', () => {
    render(
      <WorkflowVisualization
        caseId="case-1"
        result={null}
        traceEvents={[]}
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
        traceEvents={[]}
        isLoading={false}
        error={null}
      />
    );
    expect(screen.getByText(/No active case execution/i)).toBeInTheDocument();
  });

  it('renders resolved case result with resolution amount and critic approval', () => {
    const mockResult: CaseResult = {
      case_id: 'case-demo-1',
      status: 'resolved',
      customer_response: 'Your refund of $49.99 has been approved and issued.',
      resolution: {
        type: 'refund',
        amount: 49.99,
        currency: 'USD',
      },
      confidence: 0.98,
      agents_involved: ['triage', 'investigation', 'resolution', 'critic'],
      tools_used: ['lookup_order', 'lookup_payment'],
      iterations: 4,
      critic_decision: 'approve',
      trace_id: 'trace-test-123',
    };

    const mockTraces: TraceEvent[] = [
      {
        trace_id: 'trace-test-123',
        seq: 1,
        ts: '2026-10-13T12:00:00Z',
        case_id: 'case-demo-1',
        iteration: 1,
        agent: 'triage',
        event: 'agent_decision',
        decision: 'request_investigation',
        reason_summary: 'Investigate payment captured without order.',
        confidence: 0.95,
      },
      {
        trace_id: 'trace-test-123',
        seq: 2,
        ts: '2026-10-13T12:00:01Z',
        case_id: 'case-demo-1',
        iteration: 2,
        agent: 'investigation',
        event: 'tool_call',
        tool: 'lookup_payment',
        tool_result_summary: 'Payment pay-demo-001 confirmed captured $49.99',
      },
      {
        trace_id: 'trace-test-123',
        seq: 3,
        ts: '2026-10-13T12:00:02Z',
        case_id: 'case-demo-1',
        iteration: 3,
        agent: 'critic',
        event: 'agent_decision',
        decision: 'approve',
        reason_summary: 'Evidence verified against POL-REF-001.',
        confidence: 0.99,
      },
    ];

    render(
      <WorkflowVisualization
        caseId="case-demo-1"
        result={mockResult}
        traceEvents={mockTraces}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByText('RESOLVED')).toBeInTheDocument();
    expect(screen.getByText(/Your refund of \$49\.99 has been approved/i)).toBeInTheDocument();
    expect(screen.getByText(/Audit: APPROVE/i)).toBeInTheDocument();
    expect(screen.getAllByText(/lookup_payment/i).length).toBeGreaterThan(0);
  });

  it('renders escalated case with escalation reason', () => {
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
      trace_id: 'trace-test-456',
    };

    render(
      <WorkflowVisualization
        caseId="case-demo-5"
        result={mockResult}
        traceEvents={[]}
        isLoading={false}
        error={null}
      />
    );

    expect(screen.getByText('ESCALATED')).toBeInTheDocument();
    expect(screen.getByText(/High-risk fraud alert: chargeback threat exceeds safety limits/i)).toBeInTheDocument();
  });
});

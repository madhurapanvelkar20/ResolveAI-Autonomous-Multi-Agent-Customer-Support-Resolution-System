import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as api from '../api';

vi.mock('../api');

describe('App Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.checkHealth).mockResolvedValue({
      status: 'ok',
      app: 'ResolveAI',
      version: '0.1.0',
      providers: ['ollama'],
    });
  });

  it('renders application header and displays online status', async () => {
    render(<App />);
    expect(screen.getByText('ResolveAI')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Backend: Online/i)).toBeInTheDocument();
    });
  });

  it('switches between tabs', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Backend: Online/i)).toBeInTheDocument();
    });

    const scenarioTab = screen.getByRole('button', { name: /Benchmark Scenarios/i });
    fireEvent.click(scenarioTab);
    expect(screen.getByText(/Benchmark Demo Scenarios/i)).toBeInTheDocument();

    const safetyTab = screen.getByRole('button', { name: /Safety Testing Panel/i });
    fireEvent.click(safetyTab);
    expect(screen.getByText(/Safety & Boundary Test Panel/i)).toBeInTheDocument();

    const intakeTab = screen.getByRole('button', { name: /Customer Intake/i });
    fireEvent.click(intakeTab);
    expect(screen.getByText(/Customer Case Intake/i)).toBeInTheDocument();
  });

  it('executes a demo scenario and visualizes the result', async () => {
    vi.mocked(api.runScenario).mockResolvedValue({
      scenario: 'eligible_refund',
      case_id: 'case-demo-1',
      status: 'resolved',
      result: {
        case_id: 'case-demo-1',
        status: 'resolved',
        customer_response: 'Refund processed successfully.',
        resolution: { type: 'refund', amount: 49.99, currency: 'USD' },
        confidence: 0.98,
        agents_involved: ['triage', 'investigation', 'resolution', 'critic'],
        tools_used: ['lookup_order'],
        iterations: 4,
        critic_decision: 'approve',
        trace_id: 'tr-1',
      },
      trace_path: 'traces/tr-1.jsonl',
    });

    vi.mocked(api.getCaseTrace).mockResolvedValue({
      case_id: 'case-demo-1',
      trace_id: 'tr-1',
      events: [
        {
          trace_id: 'tr-1',
          seq: 1,
          ts: '2026-10-13T10:00:00Z',
          case_id: 'case-demo-1',
          iteration: 1,
          agent: 'triage',
          event: 'agent_decision',
          reason_summary: 'Internal trace detail',
        },
      ],
      event_count: 1,
    });

    render(<App />);
    const scenarioTab = screen.getByRole('button', { name: /Benchmark Scenarios/i });
    fireEvent.click(scenarioTab);

    const runBtn = screen.getAllByRole('button', { name: /Run Scenario/i })[0];
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText('REFUND APPROVED')).toBeInTheDocument();
      expect(screen.getByText(/Your refund.*was approved/i)).toBeInTheDocument();
      expect(screen.getByText('Deterministic Mock Mode')).toBeInTheDocument();
    });
    expect(screen.queryByText(/Triage Agent|Investigation Agent|Resolution Agent|Critic Agent/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Execution Trace Timeline/i)).not.toBeInTheDocument();

    expect(api.getCaseTrace).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Safety Testing Panel/i }));
    expect(screen.getByText(/Execution Trace Timeline/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/agent_decision \(triage\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Internal trace detail/i)).toBeInTheDocument();
    });
    expect(api.getCaseTrace).toHaveBeenCalledWith('case-demo-1');
  });

  it('displays offline status, warning banner, and retry connection button when backend fails', async () => {
    vi.mocked(api.checkHealth).mockRejectedValueOnce(new Error('Network error'));
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Backend: Offline/i)).toBeInTheDocument();
      expect(screen.getByText(/Backend Unreachable:/i)).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /Retry Connection/i });
    expect(retryBtn).toBeInTheDocument();

    // Mock success for retry
    vi.mocked(api.checkHealth).mockResolvedValueOnce({
      status: 'ok',
      app: 'ResolveAI',
      version: '0.1.0',
      providers: ['ollama'],
    });

    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText(/Backend: Online/i)).toBeInTheDocument();
    });
  });

  it('polls health periodically and cleans up timer on unmount', () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');

    const { unmount } = render(<App />);
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 5000);

    unmount();
    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});


import { useState, useEffect } from 'react';
import { IntakeForm } from './components/IntakeForm';
import { ScenarioButtons } from './components/ScenarioButtons';
import { SafetyTestingPanel } from './components/SafetyTestingPanel';
import { WorkflowVisualization } from './components/WorkflowVisualization';
import { TraceTimeline } from './components/TraceTimeline';
import {
  checkHealth,
  createCase,
  runCase,
  getCaseTrace,
  runScenario,
} from './api';
import { CaseResult, TraceEvent } from './types';
import './App.css';

export function App() {
  const [healthStatus, setHealthStatus] = useState<string>('checking');
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [caseResult, setCaseResult] = useState<CaseResult | null>(null);
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'intake' | 'scenarios' | 'safety'>('intake');

  useEffect(() => {
    checkHealth()
      .then((data) => {
        setHealthStatus(data.status === 'ok' ? 'Online' : 'Degraded');
      })
      .catch(() => {
        setHealthStatus('Offline (Backend Unreachable)');
      });
  }, []);

  const handleCaseSubmit = async (payload: {
    customer_id: string;
    message: string;
    subject: string;
    channel: 'web' | 'email' | 'chat';
    ticket_id?: string;
    mock: boolean;
  }) => {
    setIsLoading(true);
    setErrorMessage(null);
    setCaseResult(null);
    setTraceEvents([]);

    try {
      // 1. Submit to API case intake
      const created = await createCase({
        customer_id: payload.customer_id,
        message: payload.message,
        subject: payload.subject,
        channel: payload.channel,
        ticket_id: payload.ticket_id,
      });

      setActiveCaseId(created.case_id);

      // 2. Execute workflow on backend
      const runRes = await runCase(created.case_id, { mock: payload.mock });
      setCaseResult(runRes.result);

      // 3. Fetch real trace events
      const traceData = await getCaseTrace(created.case_id);
      setTraceEvents(traceData.events || []);
    } catch (err: any) {
      setErrorMessage(err.message || 'Workflow execution failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunScenario = async (scenarioId: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    setCaseResult(null);
    setTraceEvents([]);

    try {
      const res = await runScenario(scenarioId);
      setActiveCaseId(res.case_id);
      setCaseResult(res.result);

      // Fetch trace events for this scenario
      const traceData = await getCaseTrace(res.case_id);
      setTraceEvents(traceData.events || []);
    } catch (err: any) {
      setErrorMessage(err.message || 'Scenario run failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTriggerTestCase = async (
    type: 'malformed_input' | 'missing_evidence' | 'safety_limit'
  ) => {
    if (type === 'malformed_input') {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        await createCase({
          customer_id: 'bad!id@#$',
          message: '   ',
        });
      } catch (err: any) {
        setErrorMessage(`Validation correctly caught malformed input: ${err.message}`);
      } finally {
        setIsLoading(false);
      }
    } else if (type === 'missing_evidence') {
      // Run the damaged product scenario with missing photo evidence
      await handleRunScenario('damaged_product');
    } else if (type === 'safety_limit') {
      // Run the fraud/high risk scenario with $800 demand
      await handleRunScenario('fraud_high_risk');
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-brand">
          <h1>ResolveAI</h1>
          <span className="header-subtitle">
            Autonomous Multi-Agent Customer Support Resolution System
          </span>
        </div>
        <div className="header-status">
          <span
            className={`status-pill ${
              healthStatus === 'Online' ? 'pill-online' : 'pill-offline'
            }`}
          >
            Backend: {healthStatus}
          </span>
        </div>
      </header>

      <main className="app-main">
        <div className="tabs-nav">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'intake' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('intake')}
          >
            Customer Intake
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'scenarios' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('scenarios')}
          >
            Benchmark Scenarios
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'safety' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('safety')}
          >
            Safety Testing Panel
          </button>
        </div>

        <div className="dashboard-grid">
          <section className="input-panel">
            {activeTab === 'intake' && (
              <IntakeForm onSubmit={handleCaseSubmit} isLoading={isLoading} />
            )}
            {activeTab === 'scenarios' && (
              <ScenarioButtons
                onRunScenario={handleRunScenario}
                isLoading={isLoading}
              />
            )}
            {activeTab === 'safety' && (
              <SafetyTestingPanel
                onTriggerTestCase={handleTriggerTestCase}
                isLoading={isLoading}
              />
            )}
          </section>

          <section className="visualization-panel">
            <WorkflowVisualization
              caseId={activeCaseId}
              result={caseResult}
              traceEvents={traceEvents}
              isLoading={isLoading}
              error={errorMessage}
            />
          </section>
        </div>

        <section className="trace-section">
          <TraceTimeline events={traceEvents} />
        </section>
      </main>
    </div>
  );
}

export default App;

import React from 'react';

interface ScenarioButtonsProps {
  onRunScenario: (scenarioId: string) => Promise<void>;
  isLoading: boolean;
}

const SCENARIOS = [
  {
    id: 'eligible_refund',
    name: '1. Eligible Refund',
    desc: 'Captured payment with verified duplicate charge. Critic approves $49.99 refund.',
    tag: 'Resolved',
    tagClass: 'badge-success',
  },
  {
    id: 'ineligible_refund',
    name: '2. Ineligible Refund',
    desc: 'Refund requested after allowable 30-day window. Critic audits and denies refund.',
    tag: 'Escalated/Denied',
    tagClass: 'badge-warning',
  },
  {
    id: 'damaged_product',
    name: '3. Damaged Product (Missing Evidence)',
    desc: 'Customer reports damage without required photo proof. Critic requests evidence.',
    tag: 'Clarification',
    tagClass: 'badge-info',
  },
  {
    id: 'delivery_delay',
    name: '4. Delivery Delay',
    desc: 'Tracking shows carrier delay past SLA window. Resolution offers store credit / apology.',
    tag: 'Resolved',
    tagClass: 'badge-success',
  },
  {
    id: 'fraud_high_risk',
    name: '5. Fraud / High-Risk Escalation',
    desc: 'Threats of chargeback, velocity anomaly, and litigation alert triage -> immediate escalation.',
    tag: 'Escalated',
    tagClass: 'badge-danger',
  },
];

export const ScenarioButtons: React.FC<ScenarioButtonsProps> = ({
  onRunScenario,
  isLoading,
}) => {
  return (
    <div className="card scenario-card">
      <h2>2. Benchmark Demo Scenarios</h2>
      <p className="subtitle">Execute one of the five standard deterministic test scenarios.</p>

      <div className="scenario-grid">
        {SCENARIOS.map((sc) => (
          <div key={sc.id} className="scenario-item">
            <div className="scenario-header">
              <h4>{sc.name}</h4>
              <span className={`badge ${sc.tagClass}`}>{sc.tag}</span>
            </div>
            <p className="scenario-desc">{sc.desc}</p>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={isLoading}
              onClick={() => onRunScenario(sc.id)}
            >
              Run Scenario
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

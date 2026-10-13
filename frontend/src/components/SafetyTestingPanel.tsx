import React, { useState } from 'react';
import { executeTool } from '../api';

interface SafetyTestingPanelProps {
  onTriggerTestCase: (type: 'malformed_input' | 'missing_evidence' | 'safety_limit') => void;
  isLoading: boolean;
}

export const SafetyTestingPanel: React.FC<SafetyTestingPanelProps> = ({
  onTriggerTestCase,
  isLoading,
}) => {
  const [toolTestOutput, setToolTestOutput] = useState<string | null>(null);
  const [testingTool, setTestingTool] = useState(false);

  const testToolFailure = async () => {
    setTestingTool(true);
    setToolTestOutput(null);
    try {
      // Intentionally request unauthorized write tool 'request_refund' as triage agent
      const res = await executeTool(
        'request_refund',
        { payment_id: 'pay-demo-001', amount: 50.0, reason: 'Unauthorized test' },
        'triage'
      );
      setToolTestOutput(JSON.stringify(res, null, 2));
    } catch (err: any) {
      setToolTestOutput(`Action Gate Blocked: ${err.message}`);
    } finally {
      setTestingTool(false);
    }
  };

  const testUnknownTool = async () => {
    setTestingTool(true);
    setToolTestOutput(null);
    try {
      const res = await executeTool('unregistered_destructive_tool', {}, 'investigation');
      setToolTestOutput(JSON.stringify(res, null, 2));
    } catch (err: any) {
      setToolTestOutput(`Rejected: ${err.message}`);
    } finally {
      setTestingTool(false);
    }
  };

  return (
    <div className="card safety-card">
      <h2>3. Safety & Boundary Test Panel</h2>
      <p className="subtitle">Deliberately stress test input validation, tool authorization, critic boundaries, and safety gates.</p>

      <div className="safety-actions">
        <button
          type="button"
          className="btn btn-outline"
          disabled={isLoading}
          onClick={() => onTriggerTestCase('malformed_input')}
        >
          Exercise Malformed Input (Illegal chars / blanks)
        </button>

        <button
          type="button"
          className="btn btn-outline"
          disabled={isLoading}
          onClick={() => onTriggerTestCase('missing_evidence')}
        >
          Exercise Missing Evidence (Critic Evidence Loop)
        </button>

        <button
          type="button"
          className="btn btn-outline"
          disabled={isLoading}
          onClick={() => onTriggerTestCase('safety_limit')}
        >
          Exercise Safety Boundary ($800 &gt; $100 Limit)
        </button>

        <button
          type="button"
          className="btn btn-outline"
          disabled={testingTool}
          onClick={testToolFailure}
        >
          {testingTool ? 'Testing...' : 'Test Action Gate (Unauthorized Tool Call)'}
        </button>

        <button
          type="button"
          className="btn btn-outline"
          disabled={testingTool}
          onClick={testUnknownTool}
        >
          Test Unknown Tool Rejection
        </button>
      </div>

      {toolTestOutput && (
        <div className="tool-test-result">
          <h4>Action Gate Gatekeeper Result:</h4>
          <pre>{toolTestOutput}</pre>
        </div>
      )}
    </div>
  );
};

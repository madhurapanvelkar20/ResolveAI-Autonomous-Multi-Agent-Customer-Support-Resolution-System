import { CaseRecord, CaseResult, DemoScenario, TraceResponse } from './types';

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      // Use fallback errorDetail
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export async function checkHealth(): Promise<{ status: string; app: string; version: string; providers: string[] }> {
  const res = await fetch(`${API_BASE_URL}/health`);
  return handleResponse(res);
}

export async function createCase(payload: {
  customer_id: string;
  message: string;
  subject?: string;
  channel?: 'web' | 'email' | 'chat';
  ticket_id?: string;
  metadata?: Record<string, any>;
}): Promise<{ case_id: string; ticket_id: string; customer_id: string; status: string }> {
  const res = await fetch(`${API_BASE_URL}/cases`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function getCase(caseId: string): Promise<CaseRecord> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}`);
  return handleResponse(res);
}

export async function runCase(
  caseId: string,
  options?: { mock?: boolean; scenario?: string }
): Promise<{ case_id: string; status: string; result: CaseResult }> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options || {}),
  });
  return handleResponse(res);
}

export async function getCaseTrace(caseId: string): Promise<TraceResponse> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/trace`);
  return handleResponse(res);
}

export async function getScenarios(): Promise<DemoScenario[]> {
  const res = await fetch(`${API_BASE_URL}/scenarios`);
  return handleResponse(res);
}

export async function runScenario(
  scenarioName: string
): Promise<{ scenario: string; case_id: string; status: string; result: CaseResult; trace_path: string }> {
  const res = await fetch(`${API_BASE_URL}/scenarios/${scenarioName}/run`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function executeTool(
  tool: string,
  args: Record<string, any>,
  agent?: string
): Promise<{ ok: boolean; data?: any; error?: string }> {
  const res = await fetch(`${API_BASE_URL}/tools/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool, args, agent }),
  });
  return handleResponse(res);
}

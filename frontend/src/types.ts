export type CaseStatus = 'open' | 'resolved' | 'escalated' | 'failed';

export interface Resolution {
  type: string;
  amount?: number | string | null;
  currency?: string | null;
  action_id?: string | null;
  details?: Record<string, any>;
}

export type CustomerTimelineStage =
  | 'case_received'
  | 'payment_verification'
  | 'order_verification'
  | 'policy_review'
  | 'evidence_check'
  | 'safety_check'
  | 'resolution_decision'
  | 'next_steps';

export interface CustomerTimelineEvent {
  stage: CustomerTimelineStage;
  outcome: string;
  explanation?: string | null;
}

export type FinancialActionStatus =
  | 'proposed'
  | 'approved'
  | 'rejected'
  | 'submitted'
  | 'completed';

export interface CaseResult {
  case_id: string;
  status: 'resolved' | 'escalated' | 'failed';
  customer_response: string;
  resolution?: Resolution | null;
  confidence: number;
  agents_involved: string[];
  tools_used: string[];
  iterations: number;
  critic_decision?: 'approve' | 'reject' | 'request_evidence' | null;
  escalation_reason?: string | null;
  trace_id: string;
  customer_summary?: string | null;
  customer_timeline?: CustomerTimelineEvent[];
  financial_action_status?: FinancialActionStatus | null;
}

export interface CaseRecord {
  case_id: string;
  ticket_id: string;
  customer_id: string;
  status: CaseStatus;
  created_at: string;
  updated_at?: string;
  result?: CaseResult | null;
  trace_id?: string | null;
}

export interface TraceEvent {
  trace_id: string;
  seq: number;
  ts: string;
  case_id: string;
  iteration: number;
  agent?: string | null;
  event: string;
  input_refs?: string[];
  tool?: string | null;
  tool_result_summary?: string | null;
  decision?: string | null;
  reason_summary?: string | null;
  confidence?: number | null;
  message?: string | null;
  latency_ms?: number | null;
  extra?: Record<string, any>;
}

export interface TraceResponse {
  case_id: string;
  trace_id: string | null;
  events: TraceEvent[];
  event_count: number;
}

export interface DemoScenario {
  id: string;
  name: string;
  description: string;
  expected_status: string;
}

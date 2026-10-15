# Customer Escalations and Safety Policy

**Policy Identifier:** POL-ESC-001
**Version:** 1.0.0
**Effective Date:** 2026-01-01
**Status:** Active (Configurable Demo Policy)

---

## 1. Purpose and Scope
This policy establishes mandatory criteria and protocols for escalating customer support cases from autonomous agents to human support specialists, tier-2 supervisors, or security/risk teams. It defines safeguards to protect customer trust, financial integrity, and operational safety.

## 2. Eligibility Conditions
A case is eligible for, or mandatorily routed to, human escalation when:
1. The case cannot be safely or conclusively resolved by autonomous workflow logic.
2. The customer issues an explicit request for human supervisor assistance.
3. The claim exceeds autonomous authority limits or triggers mandatory safety boundaries.
4. Conflicting evidence or suspicious activity prevents automated decision-making.

## 3. Explicit Time Windows and Thresholds
The following demo thresholds are centrally configured and enforced:
- **Financial Auto-Approval Limit:** Any refund, credit, or settlement proposal exceeding **$100.00 USD** must be escalated to a human supervisor.
- **Workflow Iteration Limit:** Cases reaching **12 iterations** (or configured `max_iterations`) must immediately transition to escalated status.
- **Tool Call Execution Limit:** Cases reaching **20 tool calls** (or configured `max_tool_calls`) must cease automated execution and escalate.
- **Case Wall-Clock Execution Cap:** Any workflow execution exceeding **120 seconds** (or configured `max_case_wall_time_seconds`) must terminate and escalate.
- **Agent Decision Confidence Threshold:** Any agent decision with a confidence score below **0.70** (70%) requires escalation rather than executing uncertain actions.
- **Escalation SLA:** High-risk escalations must be acknowledged by human staff within **2 business hours**; standard escalations within **24 hours**.

## 4. Required Evidence and Information
When executing a human escalation, the system must package and log:
1. `ticket_id`: Current support inquiry ID.
2. `customer_id`: Verified customer ID and account profile.
3. `escalation_reason`: Specific, unambiguous justification for why automation halted.
4. `risk_level`: Severity rating (`low`, `medium`, `high`).
5. Diagnostic trace audit containing complete history of agent decisions, tool invocations, and policy citations.

## 5. Conditions Requiring Manual Review
Manual human review is mandatory under any of the following triggers:
- Any transaction flagged with risk level `high`.
- Customer expressing profanity, abusive language, or threatening legal or regulatory litigation.
- Customer threatening an external bank chargeback or payment gateway dispute.
- Repeated failed attempts to locate or verify customer or order records in the database.
- Critic agent rejecting a proposed resolution twice in the same workflow cycle.

## 6. Conditions Prohibiting Automatic Approval
Autonomous agents are strictly prohibited from approving any case or issuing any concession when:
1. **Suspected Fraud or Account Takeover:** Any security, velocity, or identity anomaly flag is active on the account.
2. **Safety Limits Reached:** Iteration limit, tool call limit, or wall-clock timeout has triggered.
3. **Critic Rejection:** The Critic agent has rejected the proposal due to insufficient evidence or policy non-compliance. Under no condition may a case transition to `resolved` without affirmative Critic approval.
4. **Policy Conflicts:** Two or more policies appear to yield conflicting mandates.

## 7. Required Actions and Customer Support Guidance
Support agents must execute the following workflow:
1. Upon detecting an escalation condition or receiving an invalid state/action:
   - Halt further autonomous tool execution or resolution attempts.
   - Set case status to `escalated`.
   - Record explicit `escalation_reason` and assess `risk`.
2. Generate a `safety_limit` or `escalation` trace event logging the event.
3. Return a courteous customer response acknowledging that the matter has been handed over to a specialist who will follow up.
4. Update the internal ticket status in the database using `escalate_to_human`.

## 8. Examples of Eligible and Ineligible Cases

### Eligible Escalation Example:
- **Scenario:** Customer submits ticket claiming $480.00 unauthorized charge with aggressive language threatening legal action. Customer account flags indicate recent password reset and IP location jump.
- **Outcome:** Mandatory immediate escalation. Risk level is `high`, amount exceeds $100.00 USD auto-approval cap, fraud flags are present, and legal threats detected. Case escalated with comprehensive audit trace.

### Ineligible Escalation (Autonomous Resolution Permitted):
- **Scenario:** Customer inquires about tracking on a package ordered 2 days ago. No fraud flags, order lookup shows `processing` within standard shipping window.
- **Outcome:** Ineligible for human escalation. Autonomous agent provides expected delivery timeline directly without needing human intervention.

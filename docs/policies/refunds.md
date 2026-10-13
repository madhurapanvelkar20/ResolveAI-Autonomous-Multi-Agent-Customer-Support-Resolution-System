# Refund Policy

**Policy Identifier:** POL-REF-001
**Version:** 1.0.0
**Effective Date:** 2026-01-01
**Status:** Active (Configurable Demo Policy)

---

## 1. Purpose and Scope
This policy governs the issuance of monetary refunds for customer purchases made on the ResolveAI platform. It applies to all consumer orders, duplicate payment incidents, and post-delivery claims where product return or cancellation is warranted under related policies. All support personnel and autonomous agents must strictly follow these rules before initiating or approving a financial disbursement.

## 2. Eligibility Conditions
A customer is eligible for a refund only if all of the following conditions are met:
1. The transaction was successfully captured and confirmed in the payment processing ledger.
2. The refund request corresponds to a verified order with proof of payment.
3. The request is submitted within the permitted time window.
4. The requested refund amount does not exceed the remaining refundable balance on the original payment transaction.
5. The associated order or items meet the criteria defined in the Return Policy (POL-RET-001), Damaged Products Policy (POL-DAM-001), or Cancellation Policy (POL-CAN-001).

## 3. Explicit Time Windows and Thresholds
The following demo thresholds are centrally configured and enforced:
- **Refund Eligibility Window:** Requests must be filed within **30 calendar days** from the transaction date or verified delivery date, whichever is later.
- **Autonomous Auto-Approval Cap:** Autonomous agents may automatically approve and disburse refunds up to **$100.00 USD** per ticket, provided all eligibility criteria and safety checks pass.
- **Supervisor Review Threshold:** Any refund exceeding **$100.00 USD** and up to **$1,000.00 USD** requires human supervisor authorization.
- **System Hard Limit:** No refund exceeding **$1,000.00 USD** can be processed through automated support tooling under any circumstances.
- **Processing Window:** Approved refunds must be credited to the original payment instrument within **5 to 10 business days**.

## 4. Required Evidence and Information
Before any refund proposal or approval is created, the system must collect and verify:
1. `ticket_id`: Unique identifier of the support inquiry.
2. `customer_id`: Verified customer account record.
3. `order_id`: Order identifier matching customer records.
4. `payment_id`: Verified payment transaction identifier showing status `paid`.
5. `refund_amount`: Specific monetary amount, matching or below remaining transaction balance.
6. `justification`: Detailed business reason citing evidence and policy section.

## 5. Conditions Requiring Manual Review
Manual human review is mandatory under the following conditions:
- The requested refund amount exceeds the auto-approval threshold ($100.00 USD).
- The payment record shows prior partial refunds or disputed line items.
- The transaction occurred between 31 and 60 calendar days ago (exceptional review).
- The customer account has opened more than 3 refund requests within the last 90 calendar days.
- The item was purchased as part of a bundle or promotional discount.

## 6. Conditions Prohibiting Automatic Approval
Autonomous agents are strictly prohibited from approving a refund under any of the following circumstances:
1. **Suspected Fraud:** The customer or transaction is flagged for suspected fraud, chargeback risk, or identity mismatch.
2. **Exceeded Window:** The request is made more than 60 calendar days after transaction or delivery date.
3. **Missing Payment Confirmation:** Payment status is `pending`, `failed`, or already fully `refunded`.
4. **No Verified Evidence:** No proof of purchase, order confirmation, or delivery failure is recorded.
5. **Customer Request Alone:** A refund must never be approved merely because a customer demands it without policy-compliant evidence.

## 7. Required Actions and Customer Support Guidance
Support agents must execute the following workflow:
1. Perform `lookup_customer`, `lookup_order`, and `lookup_payment` to verify ledger facts.
2. Query knowledge base policy citations (`search_knowledge_base`) to confirm criteria.
3. If refund amount is <= $100.00 USD and no disqualifying conditions exist, propose refund via resolution agent for critic review.
4. If refund amount exceeds $100.00 USD or manual review conditions are triggered, escalate to human support with full diagnostic notes.
5. Record internal notes detailing the calculation, payment ID, and policy reference.

## 8. Examples of Eligible and Ineligible Cases

### Eligible Case Example:
- **Scenario:** Customer Alex Morgan requests a refund of $49.99 for an order where payment was captured twice due to a gateway timeout (Payment ID: `pay-demo-001`). Request filed 2 days after order.
- **Outcome:** Eligible for autonomous refund. Amount is <= $100.00 USD, within 30-day window, ledger confirms duplicate charge, and account risk is low.

### Ineligible Case Example:
- **Scenario:** Customer demands an immediate $450.00 refund on a high-end monitor delivered 45 days ago, claiming dissatisfaction without returning the item. Customer account has a high-risk fraud flag.
- **Outcome:** Automatic approval strictly prohibited. Exceeds auto-approval cap ($100.00 USD), exceeds 30-day window, lacks return proof, and account is flagged for fraud. Immediate escalation to human fraud review team required.

# Payment Policy

**Policy Identifier:** POL-PAY-001
**Version:** 1.0.0
**Effective Date:** 2026-01-01
**Status:** Active (Configurable Demo Policy)

---

## 1. Purpose and Scope
This policy regulates payment processing, billing discrepancies, duplicate transactions, charge authorizations, and dispute management across all supported checkout channels on ResolveAI. It establishes standards for identifying billing anomalies and taking corrective action while protecting against financial loss and fraud.

## 2. Eligibility Conditions
Adjustments, corrections, or payment resolutions are permitted only when:
1. The transaction exists in the system database under `payments` table with matching customer record.
2. A legitimate billing error is confirmed via system logs, such as:
   - Duplicate charge for the same order reference within a tight timeframe.
   - Charged amount exceeding confirmed order checkout total.
   - Payment captured on a failed, abandoned, or cancelled order.
3. The payment is in `paid` or `captured` state (unsettled pending authorizations expire automatically).

## 3. Explicit Time Windows and Thresholds
The following demo thresholds are centrally configured and enforced:
- **Duplicate Charge Reporting Window:** Duplicate payment claims must be initiated within **72 hours** of transaction authorization, with a maximum claim ceiling of **30 calendar days**.
- **Automated Discrepancy Adjustment Threshold:** Autonomous agents may automatically adjust or refund billing discrepancies up to **$20.00 USD** if ledger math confirms an overcharge.
- **Duplicate Payment Auto-Refund Cap:** For confirmed identical duplicate charges, autonomous refund of the redundant charge is permitted up to **$100.00 USD** under POL-REF-001.
- **Pending Authorization Void Window:** Temporary payment holds or failed checkout authorizations drop off automatically within **7 business days** according to issuing bank policies.
- **Chargeback Dispute Window:** Customers filing external bank chargebacks bypass internal resolution and transition the ticket to legal/risk review immediately.

## 4. Required Evidence and Information
Before investigating or adjusting a payment issue, support systems must verify:
1. `payment_id`: Primary transaction identifier.
2. `order_id`: Associated order reference.
3. `amount` and `currency`: Captured numeric currency amounts.
4. `status`: Current status (`paid`, `pending`, `refunded`, `failed`).
5. Transaction timestamps and payment gateway authorization identifiers.

## 5. Conditions Requiring Manual Review
Manual review by finance/billing operations is required if:
- The payment discrepancy exceeds **$20.00 USD** (excluding confirmed duplicate charges).
- The billing issue involves multi-currency conversion variations.
- Multiple payment methods were split on a single transaction.
- More than two duplicate authorizations appear on a single customer statement.

## 6. Conditions Prohibiting Automatic Approval
Automatic payment resolution is strictly forbidden under the following conditions:
1. **Active Chargeback / Retrieval Request:** If a bank dispute or chargeback is detected, any automated refund is blocked to prevent double loss.
2. **Suspected Fraud:** Velocity alerts triggered (> 3 failed authorization attempts in 1 hour) or identity mismatch flags.
3. **Uncaptured Authorizations:** Temporary authorization holds cannot be refunded; agents must inform customer that banks release holds automatically.
4. **Third-Party Payment Gateways with External Claims:** External PayPal, Klarna, or Affirm disputes open outside our portal.

## 7. Required Actions and Customer Support Guidance
Support agents must execute the following workflow:
1. Call `lookup_payment` and `lookup_order` to cross-reference transactions.
2. Identify whether charges represent true duplicate captures or a pending hold plus settled charge.
3. If confirmed duplicate charge where both settled and amount <= $100.00 USD:
   - Propose refund for the second duplicate charge referencing POL-PAY-001 and POL-REF-001.
4. If transaction is merely pending without capture:
   - Explain authorization hold drop-off timelines (typically 3-5 business days).
5. If fraud alerts or chargeback threats are present:
   - Escalate immediately under POL-ESC-001.

## 8. Examples of Eligible and Ineligible Cases

### Eligible Case Example:
- **Scenario:** Customer was charged $35.00 twice for order `ord-demo-301` within 4 minutes due to web checkout retry. Both transactions show status `paid`.
- **Outcome:** Eligible for automated duplicate resolution. Second payment `pay-demo-302` ($35.00) is refunded immediately to the customer's card.

### Ineligible Case Example:
- **Scenario:** Customer claims a $320.00 payment was unauthorized, demands an instant cash refund, and threatens an immediate credit card chargeback. The account was created 1 hour prior.
- **Outcome:** Ineligible for automated resolution. Triggers suspected fraud, chargeback risk, and exceeds auto-refund threshold ($100.00 USD). Escalate ticket directly to human fraud operations.

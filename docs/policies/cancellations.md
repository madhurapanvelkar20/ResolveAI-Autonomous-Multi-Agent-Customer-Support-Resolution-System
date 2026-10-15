# Cancellation Policy

**Policy Identifier:** POL-CAN-001
**Version:** 1.0.0
**Effective Date:** 2026-01-01
**Status:** Active (Configurable Demo Policy)

---

## 1. Purpose and Scope
This policy governs requests to cancel customer orders before delivery. It applies to all standard retail, expedited, and promotional purchases on the ResolveAI platform. The objective is to allow timely order cancellations without disrupting warehouse fulfillment or dispatch logistics.

## 2. Eligibility Conditions
An order is eligible for cancellation if all of the following conditions are met:
1. The order status in the system is strictly `processing` or `pending`.
2. The order has not yet been assigned to carrier transit (status is not `shipped` or `delivered`).
3. The request is submitted within the established cancellation cutoff window.
4. The customer account is verified and has no pending fraud investigations.

## 3. Explicit Time Windows and Thresholds
The following demo thresholds are centrally configured and enforced:
- **Cancellation Cutoff Window:** Cancellation requests must be submitted within **24 hours** of order placement, or prior to fulfillment dispatch, whichever occurs first.
- **Warehouse Cutoff:** Once warehouse status transitions to `shipped` (or tracking label is generated), automatic cancellation is barred.
- **Refund Timeline on Cancellation:** When a cancellation is successfully executed, 100% of the authorized or captured payment is refunded within **3 to 5 business days**.

## 4. Required Evidence and Information
Before confirming an order cancellation, support agents must verify:
1. `ticket_id`: Unique support ticket ID.
2. `order_id`: The target order identifier.
3. `order_status`: Verified current status from order lookup tool.
4. `customer_id`: Proof that the requesting customer owns the order.
5. Timestamp of order placement vs timestamp of cancellation inquiry.

## 5. Conditions Requiring Manual Review
Manual review by operations or support leads is required if:
- The order status recently changed to `shipped` within the past 60 minutes and carrier recall may be possible.
- The order includes personalized, custom-manufactured, or perishable items.
- The total order value exceeds **$500.00 USD**.

## 6. Conditions Prohibiting Automatic Approval
Autonomous agents must not approve order cancellation if:
1. **Order Already Shipped or Delivered:** Order status is `shipped` or `delivered`. Customers must be directed to Return Policy (POL-RET-001) upon package receipt.
2. **Order Already Cancelled:** The order was previously cancelled and recorded in ledger.
3. **Suspected Account Takeover:** Customer email or security credentials changed within 24 hours of cancellation request.

## 7. Required Actions and Customer Support Guidance
Support agents must execute the following workflow:
1. Call `lookup_order` using the verified `order_id`.
2. Check `order.status`.
3. If status is `processing` and within 24 hours:
   - Propose order status update to `cancelled`.
   - Propose full refund of captured charges under POL-REF-001.
4. If status is `shipped`:
   - Inform the customer that the order is already in transit.
   - Provide carrier tracking information.
   - Instruct customer on how to initiate a return under POL-RET-001 once delivered.

## 8. Examples of Eligible and Ineligible Cases

### Eligible Case Example:
- **Scenario:** Customer places order `ord-demo-101` for a jacket 3 hours ago. Order status is `processing`. Customer requests immediate cancellation due to incorrect sizing.
- **Outcome:** Eligible for automatic cancellation. Order is in `processing` state, within the 24-hour window, and full payment refund is processed automatically.

### Ineligible Case Example:
- **Scenario:** Customer submits ticket requesting cancellation for order `ord-demo-102`. System lookup confirms the item shipped yesterday with carrier tracking number active.
- **Outcome:** Ineligible for cancellation. The item has already shipped. The agent explains the shipment status and provides return instructions under POL-RET-001.

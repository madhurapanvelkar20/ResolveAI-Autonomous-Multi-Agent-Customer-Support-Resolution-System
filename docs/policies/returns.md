# Return Policy

**Policy Identifier:** POL-RET-001
**Version:** 1.0.0
**Effective Date:** 2026-01-01
**Status:** Active (Configurable Demo Policy)

---

## 1. Purpose and Scope
This policy defines the terms under which delivered physical goods may be returned for a replacement, store credit, or monetary refund. It covers all physical merchandise sold directly through ResolveAI merchant channels.

## 2. Eligibility Conditions
A returned item is eligible for processing if all of the following requirements are met:
1. The order status in the database confirms `delivered`.
2. The return is initiated within the allowable return window.
3. The item is in original condition, unwashed, unworn, and includes all original tags, accessories, and packaging.
4. The product is not listed on the non-returnable items exclusion list (e.g., clearance finals, gift cards, intimate apparel, software licenses).
5. A valid Return Merchandise Authorization (RMA) or return ticket is generated before shipping back.

## 3. Explicit Time Windows and Thresholds
The following demo thresholds are centrally configured and enforced:
- **Return Request Window:** Requests must be filed within **30 calendar days** from verified delivery confirmation.
- **Physical Return Window:** Customers have **14 calendar days** from RMA issuance to drop off the parcel with the carrier.
- **Auto-Approval Return Label Threshold:** Return shipping labels may be automatically authorized for items valued up to **$250.00 USD**.
- **Supervisor Approval for Returns:** Returns for orders valued over **$250.00 USD** require manual supervisor review before return label creation.
- **Return Processing & Refund Window:** Once received and inspected at the fulfillment center, refunds are initiated within **3 to 7 business days**.

## 4. Required Evidence and Information
To process a return inquiry, the agent must collect and verify:
1. `ticket_id`: Current support ticket ID.
2. `order_id`: Associated delivered order ID.
3. `item_id`: Specific product SKU and quantity to return.
4. `return_reason`: Categorized reason (e.g., wrong size, unwanted, changed mind, defective).
5. Delivery verification date via `lookup_order`.

## 5. Conditions Requiring Manual Review
Manual review by a customer support representative is required if:
- The return request is submitted between 31 and 45 calendar days after delivery.
- The item value exceeds **$250.00 USD**.
- The customer has a history of high return rates (> 65% of all orders returned in past 180 days).
- The item was damaged in transit (must route to Damaged Products Policy POL-DAM-001).

## 6. Conditions Prohibiting Automatic Approval
Automatic approval of returns is strictly prohibited when:
1. **Window Expired:** More than 45 calendar days have elapsed since verified delivery date.
2. **Excluded Category:** Item is categorized as final sale, perishable, hygienic, or customized.
3. **Suspected Abuse / Wardrobing:** Account exhibits signs of serial return abuse or tag-reattachment fraud.
4. **Order Not Delivered:** Order is currently `processing` or `shipped` (must use cancellation or delivery policies).

## 7. Required Actions and Customer Support Guidance
Support agents must execute the following workflow:
1. Call `lookup_order` to confirm delivery status and timestamp.
2. Verify item eligibility and calculate elapsed days from delivery date.
3. If within 30 days and item value <= $250.00 USD:
   - Provide standard return shipping label and packing instructions.
   - Set ticket status to `in_progress` pending return carrier receipt.
4. If item was received damaged or defective, cross-reference POL-DAM-001 to assess fee waiver or instant replacement without return.
5. If outside window or non-returnable, politely decline and provide policy explanation.

## 8. Examples of Eligible and Ineligible Cases

### Eligible Case Example:
- **Scenario:** Customer received sneakers (Order `ord-demo-201`, value $85.00) 12 days ago. Size is slightly too large; customer requests return for refund.
- **Outcome:** Eligible for automated return authorization. Delivered within 30 days, value under $250.00 USD threshold, non-exclusion item. Return label generated.

### Ineligible Case Example:
- **Scenario:** Customer submits return request for a formal evening dress purchased 75 days ago, stating it was worn once for an event and is no longer needed.
- **Outcome:** Ineligible for return. Exceeds the 30-day window and violates unworn condition requirement. Request is rejected with polite citation of POL-RET-001.

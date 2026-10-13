# Delivery and Shipping Policy

**Policy Identifier:** POL-DEL-001
**Version:** 1.0.0
**Effective Date:** 2026-01-01
**Status:** Active (Configurable Demo Policy)

---

## 1. Purpose and Scope
This policy establishes guidelines for managing delivery delays, lost shipments, tracking updates, and transit exceptions for merchandise ordered through ResolveAI. It coordinates expectations between customers, logistics carriers, and customer support agents.

## 2. Eligibility Conditions
A delivery exception claim or resolution is eligible for processing when:
1. The target order has been marked as `shipped` with an assigned carrier tracking number.
2. The carrier tracking shows no progress, transit stagnation, or tracking status indicates exception.
3. The claim is submitted after the reasonable carrier processing window has elapsed.
4. The destination shipping address provided by the customer at checkout was valid and complete.

## 3. Explicit Time Windows and Thresholds
The following demo thresholds are centrally configured and enforced:
- **Standard Delivery Window:** Standard ground shipping takes **3 to 7 business days** from the dispatch date.
- **Estimated Delivery Date (EDD) Delay Threshold:** A package is officially deemed delayed once **5 business days** have passed beyond the carrier's published EDD without delivery or scanning activity.
- **Lost in Transit (LIT) Declaration Threshold:** If tracking displays no scan updates for **10 consecutive calendar days**, the package is declared Lost in Transit.
- **Autonomous Reshipment / Refund Cap:** For orders declared Lost in Transit valued up to **$100.00 USD**, autonomous agents may authorize a free replacement shipment or full refund.
- **Delivery Inquiry Filing Window:** Delivery issue claims must be opened within **21 calendar days** of the last carrier tracking scan.

## 4. Required Evidence and Information
To assess a delivery issue, the agent must obtain and confirm:
1. `ticket_id`: Current support inquiry ID.
2. `order_id`: Associated order reference.
3. Carrier name and tracking number.
4. Estimated Delivery Date (EDD) and date of last carrier transit scan.
5. Shipping destination address validation.

## 5. Conditions Requiring Manual Review
Manual review by a shipping logistics specialist is required if:
- Tracking shows `delivered`, but customer states parcel was not received (porch piracy or misdelivery investigation).
- Order value exceeds **$200.00 USD**.
- The carrier has opened a formal tracer or investigation requiring carrier insurance filing.
- The destination is an international or freight-forwarder address.

## 6. Conditions Prohibiting Automatic Approval
Autonomous agents must not automatically approve claims under the following circumstances:
1. **Premature Inquiry:** Package is still within standard delivery window or less than 5 business days past EDD with normal scans.
2. **Customer Address Error:** Delivery failure caused by incorrect street address, missing apartment number, or customer refusal at door.
3. **Severe Weather / Force Majeure:** Carrier has declared formal weather delay advisory affecting transit corridor.
4. **Delivered with Signature Proof:** Carrier provides biometric or physical signature confirmation from recipient.

## 7. Required Actions and Customer Support Guidance
Support agents must execute the following workflow:
1. Call `lookup_order` to verify dispatch date and tracking information.
2. Check current date against EDD and calculate transit elapsed business days.
3. If elapsed time is less than 5 business days past EDD:
   - Reassure customer and provide carrier tracking link.
   - Request customer wait until the 5-business-day delay threshold is reached.
4. If elapsed time exceeds 5 business days past EDD but under 10 days:
   - Initiate carrier trace; set ticket to `in_progress`.
5. If package is without scans for 10+ calendar days (Lost in Transit):
   - If order total <= $100.00 USD, propose replacement or refund under POL-REF-001.
   - If order total > $100.00 USD, escalate to human operations.

## 8. Examples of Eligible and Ineligible Cases

### Eligible Case Example:
- **Scenario:** Order `ord-demo-401` ($65.00) shipped 14 calendar days ago with an EDD of 8 business days ago. Carrier tracking has shown no movement or scan update for the past 11 days.
- **Outcome:** Eligible for automated Lost in Transit resolution. Order value is under $100.00 USD threshold and meets the 10-day no-scan rule. Agent authorizes replacement shipment or refund.

### Ineligible Case Example:
- **Scenario:** Customer places order on Tuesday with standard 3-7 day delivery. On Thursday (2 business days later), customer opens ticket complaining package has not arrived and demanding an immediate refund.
- **Outcome:** Ineligible for compensation or refund. Package is well within standard delivery window. Agent provides tracking link and explains anticipated arrival date.

# Damaged and Defective Products Policy

**Policy Identifier:** POL-DAM-001
**Version:** 1.0.0
**Effective Date:** 2026-01-01
**Status:** Active (Configurable Demo Policy)

---

## 1. Purpose and Scope
This policy defines the protocol for processing claims regarding merchandise delivered in damaged, broken, shattered, or factory-defective condition. It outlines evidence standards, resolution pathways (replacement vs refund), and threshold limits for immediate customer accommodation.

## 2. Eligibility Conditions
A damaged or defective merchandise claim is eligible for resolution when:
1. The item was purchased directly through an authorized ResolveAI channel.
2. The customer reported the damage within the mandatory reporting time window.
3. The customer provides verified photographic or visual evidence depicting both the damaged item and the shipping container.
4. The damage is determined to be transit-related or manufacturing defect, not user-inflicted misuse.

## 3. Explicit Time Windows and Thresholds
The following demo thresholds are centrally configured and enforced:
- **Damage Reporting Window:** Customers must report physical damage or transit breakage within **7 calendar days** of carrier delivery confirmation.
- **Defective Hardware Window:** Internal manufacturing defects (non-physical transit damage) may be reported within **30 calendar days** of delivery.
- **Low-Value Immediate Replacement / Refund Cap (No Return Required):** If item retail value is **$50.00 USD or less** and verified photographic evidence is provided, autonomous agents may immediately issue a replacement or full refund without requiring physical return of the broken item.
- **High-Value Return Requirement Threshold:** For items valued above **$50.00 USD**, the damaged item must be returned to the inspection depot using a prepaid shipping label before a replacement or refund is finalized.
- **Maximum Autonomous Resolution Cap:** Autonomous agents may not issue replacements or refunds exceeding **$100.00 USD** under any circumstances without supervisor sign-off.

## 4. Required Evidence and Information
Before any replacement or refund proposal can be approved for damaged goods, the system must confirm:
1. `ticket_id`: Current support ticket ID.
2. `order_id`: Target order ID.
3. `item_sku`: Specific product SKU and quantity damaged.
4. Photographic evidence of the damaged product.
5. Photographic evidence of the outer shipping box showing carrier shipping label.
6. Brief textual description of the damage or defect.

## 5. Conditions Requiring Manual Review
Manual human review is mandatory if:
- The customer cannot or refuses to upload photographic evidence of the damage.
- The item value exceeds **$100.00 USD**.
- The customer has filed more than 2 damaged goods claims in the prior 12 months.
- The item is hazardous, fragile fine art, or high-end electronics.

## 6. Conditions Prohibiting Automatic Approval
Autonomous agents are strictly prohibited from approving a claim if:
1. **Missing Photographic Evidence:** No image or proof of damage has been submitted. The agent must request evidence (`ask_customer` or `request_evidence`) rather than approving.
2. **Expired Reporting Window:** Damage reported more than 7 calendar days after delivery date (or defect reported after 30 days).
3. **Intentional Misuse or Alteration:** Damage evidence reveals signs of modification, water damage to non-waterproof gear, or dropping.
4. **Account Fraud Flag:** The customer account is flagged for return/refund abuse or suspicious claims history.

## 7. Required Actions and Customer Support Guidance
Support agents must execute the following workflow:
1. Perform `lookup_order` to verify delivery date and order item price.
2. Evaluate submitted evidence:
   - If photographic evidence is missing: **Do not approve**. Request the customer provide clear photos of the damaged item and packaging.
   - If photographic evidence is verified and item value <= $50.00 USD:
     - Propose immediate replacement or refund without requiring return.
   - If photographic evidence is verified and item value is between $50.01 and $100.00 USD:
     - Issue prepaid return label under POL-RET-001 before replacement/refund disbursement.
   - If item value > $100.00 USD:
     - Escalate to human supervisor for case review.

## 8. Examples of Eligible and Ineligible Cases

### Eligible Case Example:
- **Scenario:** Customer receives ceramic coffee mug set (Order `ord-demo-501`, value $32.00) 3 days ago. Customer provides photos showing shattered cups inside damaged carton.
- **Outcome:** Eligible for immediate autonomous resolution. Reported within 7 days, photographic evidence supplied, value under $50.00 USD threshold. Replacement or refund approved without requiring return of broken glass.

### Ineligible Case Example:
- **Scenario:** Customer submits a ticket stating their $400.00 laptop arrived with a cracked screen 14 days ago. Customer provides no photos and demands an instant refund.
- **Outcome:** Ineligible for automated resolution. Lacks mandatory photographic evidence, exceeds 7-day reporting window, exceeds $100.00 auto-approval cap. System prompts for required evidence or escalates to human team.

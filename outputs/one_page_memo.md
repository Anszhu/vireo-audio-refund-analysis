**To:** Arjun Mehta, Finance Controller, Vireo Audio  **Re:** Refunds by reason code and agent - reconciled

**Executive finding.** The gap between your export ("well over a crore a quarter") and the helpdesk (≈₹11 lakh) is materially explained by data-quality issues in the supplied files, not by a change in refund behaviour. Legacy Freshdesk rows store money in paise (exactly 100× the helpdesk value on all 125 re-imported pairs), and 638 tickets appear twice from the migration re-import. Raw ₹23.01 crore → canonical ₹67.10 lakh; the paise unit is the dominant factor and the duplicates are secondary (bridge: `refund_reconciliation.csv`).

**Reconciled position.** ₹67.10 lakh across 2,340 refund tickets, Jan 2025-Jun 2026: **₹11.18 lakh a quarter** on average, consistent with the helpdesk figure (its derivation is undocumented). Latest quarter (2026Q2): ₹12.80 lakh.

**Drivers.** Ticket volume rather than a higher refund rate: refunds stay at 18%-23% of resolved/closed tickets while monthly tickets grew from 302 to 948. By value: GW-OTHER 43%, return-QC 18%, duplicate payment 13%, cancellation 9%. GW-OTHER is the first dropdown option and **requires review**: 879 of its 991 refunds (₹28.72 lakh of ₹29.07 lakh) exceed the ₹500 goodwill cap, and about 82% of its texts describe an ordinary reason. The data cannot show whether that is a cap/approval gap or mis-coding. No agent is an outlier against their own team (largest deviation 1.8 standard errors).

**Control issue.** Policy says a customer never gets both a refund and a replacement. 165 refund tickets carry both in the system fields (confirmed), 179 more have a note saying so (likely) and 197 are ambiguous. In the last three quarters: 109 of 1,470 refund tickets (7.4%).

**Business opportunity.** Fact: confirmed cases carry ≈₹64,643 a quarter of replacement cost. *Illustrative 1% scenario - a planning assumption, not a forecast:* ≈₹55,925 a quarter; across residual rates of 5% to 0% it is ₹21,054-₹64,643. This is small beside ≈₹13.89 lakh of quarterly refunds; the reconciliation is the larger result.

**Recommended actions.** (1) Use the canonical totals in the board pack and have IT confirm the paise unit and remove the re-import. (2) Review the 165 confirmed refund + replacement cases with Team Leads. (3) Review GW-OTHER coding and approval controls (mandatory reason code, no default). (4) Track refund + replacement leakage monthly.

**Limitation.** Independent human validation is pending and has not been represented as completed. A 40-case evidence review (an AI assistant, not a person) agreed with the classification on 37 of 40 cases, with no false positives or negatives; it is a sample, not a guarantee. Months use ticket creation date; the dataset averages approximately 644 tickets a month over 18 months, against a stated current volume of ≈650 a week (not reconciled, nothing scaled).

# Data audit

Generated from the supplied files (raw files are never modified; a SHA-256 manifest is in `data/raw_checksums.txt`).

## 1. Dataset sizes
| File | Rows | Notes |
|---|---:|---|
| tickets.csv | 12,238 | 21 columns; 01 Jan 2025 – 30 Jun 2026 |
| agents.csv | 44 | one row per agent (all `to_date` blank); `agent_id` unique |
| orders.csv | 15,000 | |
| customers.csv | 9,500 | |
| products.csv | 14 | 14 SKUs |
| support-policy.pdf | – | v3.2; §5 reason codes, §9 systems/timestamps |

## 2. Important fields
`ticket_id`, `created_at` (IST), `status`, `agent_id`, `assigned_team`, `refund_amount_inr`, `refund_reason_code`, `replacement_issued`, `customer_message`, `agent_notes`, `source_system`, `order_id` / `customer_id` + `product_sku` (joins).

## 3. Data-quality problems found
| # | Problem | Evidence | Treatment |
|---|---|---|---|
| 1 | **Mixed monetary units** | legacy_fd refund = exactly 100× helpdesk on 125/125 re-imported pairs; median refund/retail = 90 (legacy) vs 0.90 (helpdesk) | legacy ÷ 100 in `refund_amount_norm`; raw kept in `refund_amount_raw` |
| 2 | **Re-imported duplicates** | 638 ticket_ids appear twice, always once as `helpdesk` and once as `legacy_fd`; all fields identical except refund amount (×100); all 638 helpdesk copies pre-date the 14 Sep 2025 go-live | one row kept per ticket_id (helpdesk copy); dropped rows saved to `data/processed/dropped_reimport_rows.csv` |
| 3 | Missing values | `resolved_at` 622 blank (open/pending); `order_id` 4,127 blank; `csat_score` 6,729 blank (no response – excluded from averages, not zero); refund amount & code both blank on 9,773 rows | none imputed |
| 4 | `refund_amount_inr` and `refund_reason_code` null together | verified on all rows | – |
| 5 | Catch-all reason code | GW-OTHER is 42% of refunds and the first dropdown option (email thread); 809 of 991 GW-OTHER tickets have text naming a specific reason | reported, not overwritten – recorded code stays the source of record |
| 6 | GW-OTHER above the ₹500 goodwill cap (policy §5) | 991 GW-OTHER refunds worth ₹29.07 lakh in total; 879 of them (88.7%) are above ₹500 and those 879 refunds are worth ₹28.72 lakh (₹0.35 lakh sits in the ≤₹500 refunds) | reported as *requires review*; cap breach vs. mis-coding cannot be told apart from the data |
| 7 | Free text has typos/abbreviations | e.g. "rfnnd", "pkp", "rplc" | tolerant regex; abstains when unclear |
| 8 | Ticket volume looks lower than the brief | approximately 644 tickets/month in the supplied 18-month canonical dataset (11,600 tickets) vs the client's stated operating volume of ≈650 tickets/week - different concepts, not reconciled | noted as limitation; historical data not scaled |

## 4. Join strategy
* **Agents:** by `agent_id` + assignment window (`from_date` ≤ ticket date ≤ `to_date`); never by name. All 11,600 tickets match a roster row inside its window. (The roster here has one row per agent, so the window logic has no effect on this extract but is implemented for rosters with history.)
* **Orders:** exact `order_id` for 7,701 tickets; where blank, fallback `customer_id + product_sku`, choosing the latest order on/before the ticket date: 3,804 tickets; 95 tickets unmatched. Integrity: for exact joins, order customer and SKU agree with the ticket on 100% of rows.
* **Products / customers:** by `product_sku` / `customer_id`; 100% match.

## 5. Legacy vs current system
* Current helpdesk went live 14 Sep 2025 (policy §9). `legacy_fd` rows: 3,874; `helpdesk` rows: 8,364.
* `resolved_at` on legacy rows was rebuilt from a UTC event log; the duplicate pairs show identical timestamps, so no time-zone shift is visible in this extract, but to be safe **month/quarter use `created_at`**.
* `transfers` is documented as current-helpdesk-only, yet is populated for legacy rows too; not used in the refund analysis.

## 6. Duplicate / re-import detection
Key = `ticket_id`. A ticket_id present under both source systems is a re-import. Rows are otherwise identical except the refund unit, which is how the ×100 relationship was proven. No duplicate customer or order rows exist in the reference files beyond those expected (a customer/order can appear on several tickets). Near-duplicates with different ticket_ids were not searched for beyond exact ID match (not established either way).

## 7. Important assumptions
1. Refund month = ticket `created_at` month (the refund date itself is not in the data).
2. A "resolved ticket" for rates = status resolved or closed (policy §10 "attendance"). Refund counts on open/pending tickets are included in totals but not in refund rate numerators.
3. Refund value is attributed to the resolving agent (`agent_id`), per the README.
4. Replacement cost = `unit_cost_inr` + ₹340 (policy §5); refurbishment recovery not assumed.

## 8. Known limitations
See README "Limitations" and `outputs/validation_report.md` §3.

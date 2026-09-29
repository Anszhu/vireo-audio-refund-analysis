# Submission form - Vireo Audio (Set C, support tickets)

**1. What did you build, and what business outcome does it move?**
A reproducible pipeline and a 6-page Streamlit tool (including a one-page Board Pack view) that reconcile Vireo's refund numbers and report refunds by month, reason code and agent, plus an evidence-backed list of refund + replacement exceptions (policy §5). The headline result for Finance is the reconciliation: raw export ₹23.01 crore → canonical **₹67.10 lakh** (≈ ₹11.18 lakh/quarter), explained by legacy paise (×100) and 638 re-imported duplicates. The outcome it moves is refund + replacement leakage: **109 of 1,470 refund tickets (7.4%) in the last three quarters**, ≈ ₹64,643/quarter of replacement cost (fact). An *illustrative* residual of 1% would avoid ≈ ₹55,925/quarter; that 1% is a planning assumption, not a forecast (sensitivity 5%-0%: ₹21,054-₹64,643/quarter in `outputs/target_sensitivity.csv`).

**2. What does one run cost, and what would a month cost at Vireo's volume?**
One run = **₹0** paid model/API cost (rule-based, no LLM), ₹0 compute (about 1-2 s locally), ₹0 other services. Month at the client's stated volume: 650 × 4.33 = **2,814 tickets** × ₹0 = **₹0**. Optional human review of flagged cases: 4.6% of tickets flagged × 2,814 ≈ 130 cases × 3 min (my assumption) = 6.5 h × ₹165/h (policy §4) ≈ ₹1,070/month.

**3. How do you know it works?**
Four separate kinds of evidence (`outputs/validation_report.md`), not combined into one number. (A) The supplied project records 21 structural checks passing. (B) Five key totals were re-derived with Python's `csv` module and agreed with the pipeline. (C) A 100-ticket development/hold-out sample was labelled by the AI assistant: on the hold-out, both-remedy precision was 100%, 12/13 positives were found, and exception class was correct on 17/18. (D) A 40-case secondary review by Claude AI achieved 37/40 exact agreement (92.5%), with 3 disagreements, 5 reviewer-ambiguous cases, and 0 false positives/0 false negatives under the existing positive-vs-rest comparison. Claude also contributed to rule development, so this is supplemental evidence and may be optimistic; it is not independent human validation. No independent human validation was completed during the assignment window. The project records 28 passing, 0 failing, 0 skipped tests with the private data and 13 passing/15 skipped without it; those results were recorded before this packaging pass and were not rerun here because the private source data is absent from the public bundle.

**4. Did you change, narrow, or push back on the client's ask?**
Yes, at the data-audit stage (before any dashboard). (a) I reconciled first - the crore vs ₹11 lakh question is the real problem. (b) I narrowed the "by agent - who" part of the request from a ranking of who refunds most into evidence-based team and agent analysis, because roles and responsibilities differ: Returns Desk and Billing handle refunds by design and Tier 2 is measured differently (policy §6). Agents are compared only with their own team on refund rate, and **no agent is outside the normal range of their own team** (max |z| = 1.8); the anomaly flag is a review signal, not a performance ranking. (c) I narrowed "what for": GW-OTHER is 43% of value and about 82% of it names a specific reason in the text, so the dropdown alone cannot answer it; I flag it as *requires review* and do not re-code it. (d) The stated cause of the increase (Q4 "stop arguing") is not visible: refund rate is flat, volume grew, and I cannot see the +0.4 CSAT move.

**5. What is wrong with what you are handing us?**
* Independent human validation was not completed during the assignment window. Claude labelled the 100-ticket samples and performed the 40-case secondary review, while also contributing to the rules; agreement may be optimistic. Remaining ambiguity: 197 exceptions are ambiguous and text interpretation is regex-based.
* Text rules are regex; three gaps found in the hold-out were fixed and **not** re-tested on a fresh sample. Stratified-sample recall overstates population recall (random not-flagged tickets: 3/30 development and 1/22 hold-out had a missed both-remedies note).
* "Likely" cases are the agent's own words, not proof a unit shipped; some "confirmed" cases are fields-only (note silent); 53 of 173 cross-ticket "ambiguous" flags rest on an order inferred from customer+SKU.
* The opportunity is small (≈ ₹0.56 lakh/quarter vs ≈ ₹13.89 lakh of quarterly refunds) and its 1% residual is a planning assumption.
* I cannot show how the helpdesk got ₹11 lakh - only that the cleaned six-quarter average (₹11.18 lakh) is consistent. Evidence strongly supports the paise-scale interpretation, including exact ×100 reconciliation on 125/125 re-imported refund pairs plus retail-price and agent-note support. The client did not independently confirm the unit during the assignment window, so it remains a documented analytical assumption.
* Months use ticket creation, not refund date. 3,804 tickets use an unverifiable customer+SKU order fallback.
* The supplied dataset averages approximately 644 tickets/month; the client states ≈650/week. Different concepts, not reconciled or scaled.
* Roster has one row per agent, so the assignment-window logic is untested on real history. No linter/CI. Public case-level identifiers are deterministic pseudonyms; there is no public mapping table.

**6. What did you deliberately leave out, and why?**
An LLM classifier (no evidence it would beat rules on this templated text; it would add cost, keys and non-reproducibility); re-coding GW-OTHER tickets (recorded code is the source of record); ranking agents on totals; SLA/handle-time/CSAT/transfer analysis and ₹350 SLA-breach credits (not the ask); product-lot analysis (rates rest on 30-60 tickets, no clear signal); forecasting; near-duplicate search beyond exact ticket_id; visual polish. Reasons are in `DECISIONS.md`.

**7. Anything you built/found that nobody asked for?**
(a) GW-OTHER: 991 refunds worth ₹29.07 lakh in total (43.3% of canonical refund value); 879 of them (88.7%) are above the ₹500 goodwill cap (policy §5), and those 879 refunds are worth ₹28.72 lakh (42.8% of canonical refund value). A cap/approval issue or mis-coding - not distinguishable; reported as "requires review". (b) Returns Desk resolves 26% of refunds, not "the large majority"; Billing 25%. (c) 152 of 165 confirmed refund + replacement tickets sit with Tier 1 agents although policy reserves warranty-replacement approval to Tier 2 - observed, not established (flag ≠ approval). (d) Refund rate is flat at 18%-23%; volume drives value. (e) An exception list with evidence and evidence source per case (`refund_replacement_exceptions.csv`: 165 confirmed, 179 likely, 197 ambiguous). (f) A ready-to-fill human review sheet and instructions.

**8. What did you use AI for?**
Claude (Anthropic) in claude.ai chat helped with data exploration, pipeline/rule development, tests, the Streamlit app, documentation and an earlier audit. Codex desktop (GPT-6) was used for this final audit, privacy cleanup, wording updates and GitHub publication. No paid API/model calls were used; the delivered tool makes no AI/API calls. Claude helped most with rapid exploration and boilerplate; an early cross-ticket "likely" rule and first-pass regexes were discarded. The 100-ticket samples and 40-case secondary review were AI-labelled and are supplemental, not independent human validation. See `AI_USAGE.md`. Recording link (≤3 minutes): **[PASTE SCREEN RECORDING LINK]**

**9. Public Google Drive Link**
[PASTE GOOGLE DRIVE LINK]

**10. Someone picks this up Monday and you are unreachable - the three things they need to know**
1. Put the five CSVs in `data/raw/`, run `python -m src.reports` then `streamlit run app.py`; every number in the docs is regenerated from that. Never edit raw files (`data/raw_checksums.txt`).
2. Evidence strongly supports treating legacy Freshdesk money as **paise (÷100)**: exact ×100 on all 125 re-imported refund pairs plus retail-price and agent-note evidence. The client did not independently confirm the unit during the assignment window, so it remains a documented analytical assumption. The rules live in `src/normalize.py`.
3. Text-QA results are review prompts, not verdicts, and the 100-ticket validation was AI-labelled. Get a person to fill `validation/human_review.csv` (instructions alongside) and review the "likely"/"ambiguous" exceptions before anyone is approached about a specific ticket or agent.

**11. Honest hours spent**
[FILL IN - your actual hours; I cannot measure your time. Suggested breakdown: data audit __ h · pipeline/reconciliation __ h · validation __ h · tool __ h · docs/recording __ h · total __ h (cap ~5 h).]

**12. GitHub Repo Link**
https://github.com/Anszhu/vireo-audio-refund-analysis

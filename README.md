# Vireo Audio Support Refund Analysis

Reconciles Vireo's refund numbers, breaks them down by reason code and agent (fairly), flags refund+replacement policy exceptions, and ships a small Streamlit tool with validation.

## Problem
Finance's export sums to "well over a crore a quarter"; the helpdesk reports ≈ ₹11 lakh. Finance asked for monthly refunds by reason code and by agent - "who, how much, what for" - reconciled to a total, for a board pack on 24 Sep.

## Key finding (fact)
* Raw export ₹23.01 crore → canonical **₹67.10 lakh** (2,340 refund tickets, Jan 2025-Jun 2026) ≈ **₹11.18 lakh/quarter**; latest quarter (2026Q2) ₹12.80 lakh.
* Cause of the gap: legacy Freshdesk amounts are in paise (exactly ×100 on every re-imported pair) plus 638 re-imported duplicate tickets.
* Refund *rate* is flat (18%-23% of resolved/closed tickets); value grew with ticket volume.
* No agent is outside the normal range for their own team (max |z| = 1.8); the Returns Desk raises 26% of refunds.
* GW-OTHER (first dropdown option): 991 refunds, ₹29.07 lakh (43% of value) - **requires review**. 879 of them (89%) are above the ₹500 goodwill cap, and that above-cap subset is worth ₹28.72 lakh. About 82% name a specific ordinary reason in the text. This is a review signal, not a finding of mis-coding or misconduct.

## Business outcome
Primary: a reconciled, defensible refund number for the board pack. Secondary: a control opportunity on refund + replacement cases.
* **Fact:** 109 of 1,470 refund tickets (7.4%) in the last three quarters carry both a refund and a replacement (policy §5 exception); their replacement cost is ≈ ₹64,643 per quarter. A further 115 tickets have notes saying both were given but the flag is blank (≈ ₹73,080/quarter if verified).
* **Planning assumption (not proven, not a forecast):** if the rate fell from 7.4% to a residual **1%**, avoided replacement cost would be ≈ **₹55,925 per quarter**. `outputs/target_sensitivity.csv` shows 5%, 3%, 2%, 1% and 0%. The 1% target is a planning assumption, not a forecast.

## Streamlit pages
1 Executive summary · 2 Refund explorer · 3 Agent analysis · 4 Exception review (with evidence and evidence source) · 5 Data quality & reconciliation · 6 Board Pack (single screenshot-ready page).

## Architecture
```
data/raw/*.csv ─► src/ingest.py ─► src/normalize.py ─► canonical_tickets.csv
   (untouched)      (as strings)     dedupe · ÷100 legacy · order/agent/product joins
                                             │
     ┌───────────────┬───────────────┬───────┴────────┬──────────────────┬───────────────┐
 reconcile.py   refund_analysis.py  agent_analysis.py  ai_assistant.py → exceptions.py   gw_other.py · target.py
 (bridge)       (month/qtr/reason)  (team-normalised)  (text QA rules)    (confirmed/likely/ambiguous)  (review metric · sensitivity)
                                             │
     validate.py (independent csv recompute) · human_review.py (human sheet + scoring) · tests/ · app.py (Streamlit)
```

## Data sources
`tickets.csv`, `agents.csv`, `orders.csv`, `customers.csv`, `products.csv`, `support-policy.pdf`, email thread, README. **Client data is not committed**; put the five CSVs in `data/raw/` (see `data/README.md`).

## Setup
Requires Python 3.10+ (developed on 3.12).
```bash
python -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1   |  cmd: .venv\Scripts\activate.bat
pip install -r requirements.txt
```

## Running locally
```bash
# 1. copy tickets.csv agents.csv orders.csv customers.csv products.csv into data/raw/
python -m src.reports          # pipeline + reconciliation + validation report + memo + decisions + audit (≈2 s)
pytest tests/                  # automated tests
streamlit run app.py           # interactive tool
# public, aggregate-only demo (no raw inputs required):
streamlit run app_public.py
# human review (only after a person has filled validation/human_review.csv):
python -m src.human_review --score && python -m src.reports
```

## Public Streamlit deployment
The submitter reports that the public deployment was completed and manually verified. The deployed entrypoint is `app_public.py`; it reads the four sanitized aggregate CSVs from `outputs/` and does not load client raw records.

- Repository: [`Anszhu/vireo-audio-refund-analysis`](https://github.com/Anszhu/vireo-audio-refund-analysis)
- Branch: `main`
- Main file: `app_public.py`
- Public URL: [vireo-audio-refund-analysis-fab3xdggd3hytln7qxvyfa.streamlit.app](https://vireo-audio-refund-analysis-fab3xdggd3hytln7qxvyfa.streamlit.app/)

## Testing
```bash
pytest -q -rs
```
**Data-dependent tests require the supplied assignment dataset in `data/raw/`. Without that private dataset, those tests are intentionally skipped** (pytest reports them as skipped, not passed), and only the rule/scoring/static tests run. With the dataset present all tests execute; the last verified run is recorded in `FINAL_SUBMISSION_CHECKLIST.md`.

## AI usage
Text QA (`src/ai_assistant.py`) is **deterministic regex/keyword rules - no LLM, no API key, no network**; the production pipeline depends on no external model. The dropdown `refund_reason_code` remains the source of record. There is no LLM integration in this repo (only a `get_classifier()` seam). The *development* of this repo used Claude (Anthropic) in claude.ai chat - see `AI_USAGE.md`.

## Validation
Four kinds of evidence, reported separately in `outputs/validation_report.md`:
* **A. Automated:** 21 structural checks in code (all pass) · **B. Independent recomputation:** 5 totals re-derived with the `csv` module (all pass).
* **C. Development / hold-out:** 100 tickets (60 + 40) labelled **by the AI assistant, not by a human**. Hold-out: both-remedy precision 100%, 12/13 positives found; exception class 17/18; not pooled with the development sample.
* **D. 40-Case AI Secondary Review:** **40-Case AI Secondary Review** - supplemental secondary-review evidence from Claude AI, which also contributed to rule development; agreement may be optimistic. This is separate from the project-owner-reported qualitative human package review; no independent human case labels or blinded statistical validation were completed. Exact-class agreement 37/40 (92.5%; error rate 7.5%), 0 false positives, 0 false negatives, 5 reviewer-ambiguous, 3 disagreements (all existing *ambiguous* → reviewer *not_confirmed*). A sample of 40 stratified tickets, not a guarantee for every ticket. The project owner reports a separate qualitative human review of the completed package; reviewer identity, date, and independence were not supplied. This does not constitute independent human case-label validation. Details below and in `outputs/validation_report.md`.

## 40-case AI secondary review
**What was reviewed:** 40 refund tickets, sampled with a fixed seed from the 2,340 canonical refund tickets (10 classed confirmed, 10 likely, 8 ambiguous, 12 not flagged). Each was reviewed against the ticket, order, product, other tickets on the same order and the support policy (§5-§6), with the existing class hidden until after labelling. **The result applies to this stratified sample only, not to the whole dataset.**

**Who reviewed:** Claude AI assistant, which also contributed to rule development. This is supplemental secondary-review evidence, not independent human validation; agreement may be optimistic. Independent human validation was not completed during the assignment window.

**Result:** sample 40; correct 37; incorrect 3; accuracy 92.5% (95% interval 80%-97%); error rate 7.5%; false positives 0; false negatives 0; reviewer-ambiguous 5. Reviewer labels: 10 confirmed, 10 likely, 5 ambiguous, 15 not confirmed.

**Known failure cases:** the 3 disagreements are all existing *ambiguous* → reviewer *not_confirmed* (cross-ticket flags where the refund was a cancellation or payment reversal). No keyword false positives or requested-vs-issued confusions were found. The production rules and the confirmed/likely/ambiguous counts were **not** changed. A person should still re-label the sheet.

## Cost
**Paid model/API cost per run = ₹0** (no LLM or paid service is called; text QA is regex/keyword rules).
* A. LLM/API: ₹0.  B. Compute: ₹0 - one full run over 12,238 rows takes about 1-2 s on a laptop; no cloud is used.  C. Other paid services: ₹0.
* Monthly volume at the client's stated operating volume: 650 tickets/week × 4.33 weeks/month = **2,814 tickets/month**. Of these ≈20.1% carry a refund (last-3-quarter share in the data) ≈ 566 refund tickets/month. Model/API cost for the month = 2,814 × ₹0 = **₹0**. (Different concept from the 644 tickets/month historical average of the supplied dataset; not scaled.)
* D. Optional human review of the exception queue: 4.6% of tickets are flagged (confirmed+likely+ambiguous, last 3 quarters) → 0.0461 × 2,814 ≈ 130 cases/month × 3 min (**assumption**) = 6.5 h × ₹165/agent-hour (policy §4) ≈ **₹1,070/month**. A business-process cost, not a run cost; a run without review costs ₹0.

## Assumptions
1. Month/quarter = ticket `created_at` (refund date not in data). 2. Refund attributed to resolving `agent_id`. 3. "Resolved" = status resolved/closed (policy §10). 4. Replacement cost = unit cost + ₹340; no refurbishment recovery. 5. The residual 1% target is a **planning assumption**. 6. Human review 3 min/case is an assumption.

## Limitations
* The project owner reports that a human reviewer qualitatively checked the package and dashboard; identity, date, and independence were not provided. Independent human case-label validation was not completed (the 40-case secondary review and 100-ticket samples were AI-labelled).
* Rules are regex-based and will miss new phrasings; three gaps found in the hold-out were fixed without a third sample.
* "Likely" = the agent's note says both remedies were given; unit dispatch is not in the data. "Confirmed" = two fields agree; for some tickets the note is silent.
* Same-order cross-ticket replacements are only "ambiguous" (could be a separate incident); 53 of 173 rely on an order inferred from customer+SKU.
* 3,804 tickets use the customer+SKU order fallback (unverifiable); 95 unmatched.
* The supplied dataset averages approximately 644 tickets/month over 18 months; the client states ≈650 tickets/week. Different concepts, not reconciled; totals are not scaled.
* How the helpdesk's ₹11 lakh was computed is not documented - only consistency is shown.
* Roster has one row per agent, so assignment-window logic is untested on real history.
* No linter configured; no CI.

## Repository structure
```
app.py  README.md  DECISIONS.md  DATA_AUDIT.md  AI_USAGE.md  submission-form.md  FINAL_SUBMISSION_CHECKLIST.md  requirements.txt
src/      ingest · normalize · reconcile · refund_analysis · agent_analysis · ai_assistant · exceptions · gw_other · target · human_review · validate · pipeline · reports
tests/    test_pipeline.py
validation/  HUMAN_REVIEW_INSTRUCTIONS.md · human_review.csv (labels empty until a person fills them; git-ignored, contains ticket text)
          local validation CSVs (AI-labelled; git-ignored; identifiers pseudonymized)
outputs/  refund_reconciliation.{csv,md} · reconciliation_bridge_clean.csv · reason_code_summary.csv · target_sensitivity.csv · gw_other_review.csv
          one_page_memo.md · validation_report.md · demo_script.md · case-level exports (generated locally, git-ignored)
data/     README.md · raw/ (you supply, git-ignored) · processed/ (generated) · raw_checksums.txt
```

## Privacy of client data
Git-ignored: `data/raw/`, `data/processed/`, `outputs/private/` (agent names, customer messages and agent notes), `validation/private/` (full-text label files), and the optional `validation/human_review.csv` sheet. Public case-level exports use deterministic pseudonyms for ticket, customer, order, agent, and SKU identifiers; no mapping table is published. Private/local data retains source identifiers for joins and client-side review.

## Reproducibility
Pure functions, no randomness in the pipeline (the human-review sample uses a fixed seed), pinned version ranges in `requirements.txt`; `python -m src.reports` regenerates every number in the docs. `data/raw_checksums.txt` lets you confirm the raw files are the ones analysed (SHA-256).
STREAMLIT LINK : https://vireo-audio-refund-analysis-fab3xdggd3hytln7qxvyfa.streamlit.app/

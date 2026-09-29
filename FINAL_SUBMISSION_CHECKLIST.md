# Final submission checklist

`[x]` = verified in the last full run (from a clean `outputs/` and `data/processed/`, with the supplied dataset in `data/raw/`).
`[ ]` = needs your action or has not been done. Nothing below is ticked on your behalf.

Last run recorded in the supplied project (not rerun during this packaging pass): `python -m src.pipeline` (exit 0) · `python -m src.reports` (26/26 checks; memo 448 words) · `pytest -q -rs`: **28 passed, 0 failed, 0 skipped** with the data; **13 passed, 15 skipped in 0.44s** without the private dataset · `streamlit run app.py`: server healthy (HTTP 200), all 6 pages render without exceptions in a headless test, filters on pages 2 and 4 work. This environment could not launch its configured Python runtime, and the raw dataset was not available in the extracted public project.

## TECHNICAL
- [x] pipeline runs
- [x] reports regenerate
- [x] tests pass with data (28 passed, 0 skipped)
- [x] tests skip cleanly without private data (documented in README)
- [x] Streamlit runs
- [x] Board Pack works
- [x] no secrets / API keys in the repo
- [x] no private raw data in the packaged repo (`data/raw/` holds only `.gitkeep`)
- [ ] you have opened the app in a browser and looked at the Board Pack page yourself (I tested headlessly, not visually)

## ANALYTICS
- [x] refund reconciliation verified (independent `csv`-module trace: raw ₹23,01,24,081 → canonical ₹67,09,932; 2,340 refund tickets; ₹11.18 lakh/quarter)
- [x] duplicate handling verified (638 ticket_ids under both systems; helpdesk copy kept)
- [x] legacy money issue verified (exactly ×100 on 125/125 re-imported refund pairs)
- [x] bridge-order dependence stated (paise dominant either way; duplicates secondary)
- [x] agent normalization verified (agent_id + roster window, own-team comparison, no ranking)
- [x] GW-OTHER verified (991 refunds ₹29.07 lakh; 879 above ₹500 worth ₹28.72 lakh; separate definitions everywhere)
- [x] refund + replacement verified (165 confirmed / 179 likely / 197 ambiguous; last 3 quarters 109 of 1,470 = 7.4%)
- [x] sensitivity verified (1% row equals the main business case; 0% row equals total confirmed replacement cost)
- [x] Client confirmation of the legacy unit was unavailable; the paise scale is documented as a strongly supported analytical assumption

## VALIDATION
- [x] automated validation (21 structural checks pass)
- [x] independent recomputation (5 checks pass; independent of the pandas code, not of the analyst)
- [x] holdout validation (AI-labelled; reported separately from development; NOT independent human validation)
- [x] **40-case AI secondary review** by Claude AI (blind to the existing class): 37/40 exact agreement (92.5%), 5 reviewer-ambiguous, 0 FP, 0 FN under the positive-vs-rest comparison, 3 disagreements. Supplemental only; agreement may be optimistic.
- [ ] Independent human validation was not completed during the assignment window; it remains a possible follow-up, not a completed result.

## DOCUMENTATION
- [x] README
- [x] DATA_AUDIT
- [x] DECISIONS
- [x] AI_USAGE
- [x] validation report (regenerated from current code)
- [x] memo
- [x] submission form (structure and answers complete; placeholders remain for items below)
- [x] demo script
- [ ] you have re-read the memo and submission form and agree every sentence is true for your work

## SUBMISSION
- [ ] public GitHub repo created (check that `git status` shows no `data/raw/*.csv`, `outputs/private/`, `validation/private/`, `validation/human_review.csv`)
- [ ] Google Drive recording (≤3 min) recorded and shared publicly
- [ ] recording link inserted (`submission-form.md` Q8 and Q9)
- [ ] GitHub link inserted (`submission-form.md` Q12)
- [ ] honest hours inserted (`submission-form.md` Q11)
- [x] public ticket, customer, order, agent and SKU identifiers are deterministic pseudonyms; no mapping table is included

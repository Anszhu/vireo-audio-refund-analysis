# Final submission checklist

## Verified locally on 29 September 2026

- [x] `python -m src.reports` completed successfully with supplied private data present locally; 26/26 report validation checks pass.
- [x] `pytest -q -rs`: 28 passed, 0 failed, 0 skipped.
- [x] `app.py` and `app_public.py` started locally; all six pages in each were visited and key filters/interactions were exercised.
- [x] `app_public.py` smoke-tested from a folder containing only itself and the four sanitized aggregate CSVs, with no `data/raw/` directory; no browser errors or failed requests.
- [x] Canonical refund total independently recomputed as ₹67,09,932 across 2,340 refunds; reconciliation bridge closes at ₹0.
- [x] Raw input files and `validation/human_review.csv` are ignored and not tracked by Git.
- [x] The owner-reported qualitative human package review is disclosed separately from AI-labelled samples. Reviewer identity, date, and independence were not supplied; no independent human case-label validation is claimed.

## Still required from the submitter

- [ ] Record and link the screen walkthrough (maximum 3 minutes), including prompts, changes between versions, and discarded work.
- [ ] Add a public Drive link if the submission portal requires one.
- [x] Entered submitter-reported actual time: 7 hours (above the brief’s approximately 5-hour cap).
- [x] Publish the final local changes to `Anszhu/vireo-audio-refund-analysis` under the `Anszhu` GitHub identity.
- [ ] Streamlit Community Cloud deployment has not been performed. Settings: repository `Anszhu/vireo-audio-refund-analysis`, branch `main`, main file `app_public.py`.
- [ ] Obtain an independent case-level review before treating text-rule performance as statistically validated.

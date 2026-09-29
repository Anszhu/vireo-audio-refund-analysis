# Final pre-submission audit

## Current status

This audit records the local verification pass on 29 September 2026. The public GitHub repository is `https://github.com/Anszhu/vireo-audio-refund-analysis`. The user authorized publication of these final local changes to the existing public repository under the `Anszhu` identity. Streamlit Cloud deployment itself has not been performed. For Streamlit Community Cloud, use repository `Anszhu/vireo-audio-refund-analysis`, branch `main`, main file `app_public.py`; deployment itself has not been performed.

## Data handling and privacy

- Supplied client data was placed locally in `data/raw/` and the human-review sheet remains local. `git check-ignore` confirms the raw files and `validation/human_review.csv` are ignored. `git ls-files` lists only `data/raw/.gitkeep` from that directory and does not list the review sheet.
- `app_public.py` reads exactly four sanitized aggregate files: `reason_code_summary.csv`, `reconciliation_bridge_clean.csv`, `agent_totals.csv`, and `target_sensitivity.csv`. It does not load raw data, case text, full review labels, or identifier maps.
- A copy of only `app_public.py` and those four CSVs was run from a clean smoke-test folder with no `data/raw/` directory. All six pages loaded and interacted without browser errors or failed requests.
- The public aggregate app omits case-level evidence and the above-cap subset because neither is in its allowed four-file input set.

## Pipeline and test results

- `python -m src.reports`: exit 0; regenerated reports; 26/26 validation checks pass (21 structural plus 5 independent recomputations). Canonical refunds are ₹67,09,932 across 2,340 refund tickets; the reconciliation bridge is ₹0. The run completed in about 5.4 seconds locally.
- `pytest -q -rs`: **28 passed, 0 failed, 0 skipped** (3.72 seconds), with the supplied local data available.
- `python -m py_compile app_public.py`: passed.
- Both `app.py` and `app_public.py` were started locally. All six pages in each were navigated; key filters, team selection, evidence expander, and Board Pack values were checked. The existing private app's Board Pack and the public app's six pages were visually inspected. The public app was additionally isolated from raw data during its smoke test. Stopping the Windows browser sessions logged an asyncio `ConnectionResetError` after the browser disconnected; the recorded page runs had no application/page errors or failed requests.
- Initial setup required installing pytest and Streamlit into local, untracked workspace dependency folders; no project requirements were modified for those installs. No tests were added in this pass.

## Human review and model-assisted checks

- The project owner reports that a human reviewer manually checked the analysis, generated outputs, calculations, reports, and Streamlit dashboard and confirmed them. This is a qualitative package review. The reviewer's identity, role, date, and independence were not supplied, so this audit does not claim an independent or blinded case-level statistical validation.
- Separately, the 40-case review recorded in the project is AI-assisted (reviewer type `ai_assistant`): 37/40 exact class agreement, 3 disagreements, 5 reviewer-ambiguous, and 0 false positives/false negatives under the stated binary comparison. It remains secondary review, not the human review described above.
- The 100-ticket development/hold-out samples are also AI-labelled and are reported separately. Neither those nor the 40-case AI review are represented as human ground truth.

## Known limits and remaining submission items

- Text rules are deterministic regex/keyword rules. Three gaps found in hold-out were patched without a fresh third sample. “Likely” reflects agent notes, not dispatch confirmation; ambiguous cross-ticket matches and inferred order joins remain.
- The 1% replacement residual scenario is a planning assumption, not an observed or forecast saving. The legacy paise interpretation is strongly supported by internal evidence but was not independently confirmed by Vireo.
- The dashboard smoke tests were local, not a deployed Streamlit Cloud check. The final local changes are not on GitHub until the user chooses to push them.
- The submitter reports spending **7 hours**, above the brief’s approximately 5-hour cap. Screen recording and public Drive link were not provided; those fields remain to be supplied in `submission-form.md`.
- Reviewer identity/independence is not documented. A fresh, independent case-level review would strengthen the evidence before operational decisions.

# AI usage log

| Field | Detail |
|---|---|
| Tool / model | Claude (Anthropic) in the claude.ai chat interface. Model recorded in the original log as Claude Sonnet 5.5 (not independently verifiable from the repo); the later audit/finalisation pass was also done in claude.ai chat. |
| Paid APIs | **None.** No API key exists in the repo or was used. |
| Estimated cost | Not measured; used within a chat subscription. **₹0 API cost.** The delivered tool makes no AI/API calls (₹0 per run). |
| Production pipeline depends on an external model? | **No.** Text QA is deterministic regex/keyword rules in `src/ai_assistant.py`; there is no LLM integration (only a `get_classifier()` seam). `tests/test_pipeline.py` fails if network or LLM-client imports appear under `src/`. |

## Where AI helped
* `src/*.py`, `app.py`, `tests/test_pipeline.py`, the generated documents, fast data profiling (spotting ×100 legacy scaling and exact duplicate pairs), and test generation.
* An audit pass over the finished repo: found that an earlier tickets-per-month statement had been computed on resolved/closed tickets only instead of on all canonical tickets (≈644/month); that 53 of 173 cross-ticket "ambiguous" flags rely on an inferred order id; and that validation files contained customer free text and agent names. Added the sensitivity table, GW-OTHER review metric, exception evidence columns, Board Pack page, human-review workflow and DECISIONS.md.

## Where AI was not useful
Regex iteration (three rounds on the text rules) took longer than expected; one over-confident rule (below). AI-assigned labels cannot stand in for a person's judgement - they were useful for finding rule bugs only.

## What was accepted
Pipeline structure (dedupe → ÷100 legacy → joins), the bridge/reconciliation, team-normalised agent metrics, exception classes, tests, app layout.

## What was modified / corrected
* Exception rule: the first version treated refund tickets sharing an order with another ticket's replacement as "likely" - **downgraded to "ambiguous"** (could be a separate incident; currently 173 cases).
* Topic regexes: fixed after the development sample (e.g. "reverse pickup arranged" mis-read as refund delay; "refund not received" read as lost parcel).
* Both-remedy regex: added "fresh unit shipped", "also sending a new set", "rfnd only" (as a *decline*), "pkp missed" after sample review.
* Audit pass: tickets-per-month wording corrected to ≈644 (all canonical tickets over 18 months); the 1% target relabelled as a planning assumption; AI-labelled samples no longer described as manually checked; text-bearing files moved out of the committed set.
* Memo/README numbers are generated from code (`python -m src.reports`) to prevent hand-typed errors.

## Role of AI in the 40-case AI secondary review
Claude produced the labels described in `outputs/validation_report.md` after reading evidence packs with the existing class hidden. This is a second-pass QA review by an assistant that also wrote the rules, so it is not independent. It helped by re-reading every ticket, its order history and the policy; it could not replace a person's judgement on what actually shipped (no fulfilment data exists). It surfaced a candidate rule refinement that was **considered and not applied** (3 disagreements, not separable by reason code), and an out-of-scope observation (same-amount refunds on one order).

## What was discarded
An LLM-classifier stub (unused, removed); the cross-ticket "likely" classification; first-pass regexes; deprecated Streamlit arguments.

## Honesty notes
* The same AI wrote the rules and labelled the 100-ticket validation samples - **not independent**.
* **40-case AI secondary review:** the 40 labels were produced by Claude (the AI assistant), working blind to the existing class, and are recorded as `reviewer_type = ai_assistant`. **AI did not perform independent human validation**; that remains pending and has not been represented as completed. A person should overwrite the labels.
* Numbers in the docs come from code output; interpretation of "likely" and "confirmed" should be reviewed by a person.

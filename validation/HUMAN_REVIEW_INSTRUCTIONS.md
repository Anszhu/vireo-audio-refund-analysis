# Human review instructions - refund + replacement flags (40 cases)

**Status: independent human validation is pending and has not been represented as completed.**
`validation/human_review.csv` currently holds an **AI-assistant review** of the 40 cases (`reviewer_type = ai_assistant`), produced blind to the existing class. It is not independent and not a person's validation. A blank copy of the sheet is in `validation/private/human_review_blank_template.csv` (git-ignored) - copy it over `human_review.csv`, then follow the steps below to replace the AI labels with your own.

## The question you answer for each ticket
Using **only the evidence on the sheet**: did this customer get **both a refund and a replacement for the same order** (policy §5 says never both)? Then record how sure the evidence lets you be.

## Before you start
1. Open `validation/human_review.csv` in Excel or Google Sheets (UTF-8).
2. **Hide the last column, `existing_prediction`.** Do not look at it until all 40 rows are labelled. Seeing it anchors your judgement and ruins the test.
3. Fill in only the columns listed below. Do not delete rows, rename columns or edit the evidence columns. If you sort, sort whole rows.
4. Customer and agent names have been replaced with `[CUSTOMER]` / `[AGENT]`. No personal names are needed for the review.

## What you can see
`ticket_id` · `refund_amount_inr` (rupees; legacy amounts already divided by 100) · `refund_reason_code` · `replacement_issued` (the agent's Y/N flag) · `agent_id` · `created_at` · `order_id_basis` (*quoted on ticket* = reliable; *inferred (customer+SKU)* = a pipeline guess; *none*) · `product_name` · `other_tickets_same_order` (other tickets on the same order, with their refund and replacement flags) · `customer_message` · `agent_notes`.
To read another ticket in full, look up its id in `data/raw/tickets.csv`.

## What you fill in
### `human_label` - type exactly one of these four words
| Label | Choose it when |
|---|---|
| `confirmed` | Refund on this ticket **and** `replacement_issued = Y`, and neither note nor message says the replacement was declined, rejected or never sent. |
| `likely` | `replacement_issued = N`, but the agent note clearly says a replacement / new unit was **also** sent or dispatched with the refund. |
| `ambiguous` | The evidence conflicts or does not settle it: flag `Y` but the note says the replacement was declined; a replacement is only mentioned, not said to be sent; or the replacement sits on a *different* ticket of the same order (could be a separate incident). |
| `not_confirmed` | Nothing on the sheet shows both remedies for this order. |

Judge from the evidence, not from what you guess the rules did. If you would not defend a `confirmed` to Finance, use `ambiguous`.

### The other columns
| Column | Values |
|---|---|
| `human_confidence` | `high` (evidence explicit) · `medium` (reasonable reading, some doubt) · `low` (a guess) |
| `evidence_basis` | one sentence: what the evidence shows |
| `evidence_source` | e.g. `structured flag + agent note`, `related ticket` |
| `reasoning` / `policy_reference` | one sentence of reasoning; e.g. `Support policy §5` |
| `reviewer_type` | `independent` (you did not build or tune the rules) · `author` (you did) - be honest; `ai_assistant` marks the AI-produced labels. Only `independent` rows count as independent |
| `review_notes` | Optional, one short sentence. No names, no long quotes. |
| `correct` | **Leave blank.** The script fills it (`Yes` if your label equals `existing_prediction`, else `No`). |

## Invented examples (not from the data)
* Flag `Y`, note "refund processed; replacement unit also shipped" → `confirmed` · `high` · `both`
* Flag `N`, note "issued refund and sent a fresh unit as goodwill" → `likely` · `high` · `text`
* Flag `Y`, note "replacement rejected, refund only" → `ambiguous` · `medium` · `both`
* Flag `N`, note "cancelled before dispatch, refunded", no other tickets → `not_confirmed` · `high` · `both`

## When all 40 are done
```bash
python -m src.human_review --score    # fills `correct`, prints the summary
python -m src.reports                 # regenerates validation_report.md section D and every document
```
The report then shows: sample size, correct, incorrect, cases you labelled `ambiguous`, accuracy (95% interval), error rate, false positives, false negatives. "Positive" = `confirmed` or `likely`. A false positive is a rule-positive you did not label positive; a false negative is a rule-negative you labelled positive. `python -m src.reports` also writes `validation/review_summary.csv` (aggregate counts only) and `validation/review_disagreements.csv`. A partly filled sheet is reported as **partial**; an empty one stays **pending**. Column set of the completed sheet: `ticket_id, existing_prediction, human_label, human_confidence, evidence_basis, evidence_source, reasoning, policy_reference, correct, review_notes, reviewer_type`; the blank template also carries the redacted evidence columns you need while reviewing.

## Limits to state honestly
40 cases is small, so the interval is wide. The 12 unflagged tickets can only reveal a large miss rate. The sample is stratified (flagged cases over-represented), so the accuracy is not population accuracy. `human_review.csv` holds ticket ids and case reasoning (the blank template also holds redacted ticket text) and is git-ignored; publish only the aggregate `review_summary.csv`.

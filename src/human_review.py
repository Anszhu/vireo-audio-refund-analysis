"""Independent human-review workflow for refund + replacement flags.

NOTHING in this module invents review results. `--init` writes a sheet with the label columns EMPTY;
a person fills them in; `--score` (or `python -m src.reports`) then computes the metrics.
Until labels exist the validation report says: "Independent human validation pending."

  python -m src.human_review --init     create validation/human_review.csv (refuses to overwrite)
  python -m src.human_review --score    fill the `correct` column and print the summary
"""
import argparse
import math
import re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REVIEW_CSV = ROOT / "validation" / "human_review.csv"
SEED = 2026
SAMPLE_PLAN = {"confirmed": 10, "likely": 10, "ambiguous": 8, "not_confirmed": 12}   # 40 cases
LABELS = ["confirmed", "likely", "ambiguous", "not_confirmed"]
CONFIDENCE = ["high", "medium", "low"]
EVIDENCE_BASIS = ["structured", "text", "both", "cross_ticket", "none"]
REVIEWER_TYPES = ["independent", "author", "ai_assistant"]   # only "independent" counts as independent human validation
POSITIVE = {"confirmed", "likely"}
# Reviewer sees everything except the prediction; `existing_prediction` is the LAST column on purpose (hide it first).
COLUMNS = ["ticket_id", "refund_amount_inr", "refund_reason_code", "replacement_issued", "agent_id", "created_at", "order_id_basis",
           "product_name", "other_tickets_same_order", "customer_message", "agent_notes",
           "human_label", "human_confidence", "evidence_basis", "evidence_source", "reasoning", "policy_reference",
           "reviewer_type", "correct", "review_notes", "existing_prediction"]
# The completed review file keeps only: ticket_id, existing_prediction, human_label, human_confidence, evidence_basis,
# evidence_source, reasoning, policy_reference, correct, review_notes, reviewer_type  (no customer text).


def _agent_name_tokens(agents):
    if agents is None:
        return []
    toks = set()
    for n in agents["name"].dropna():
        toks.add(n.strip())
        toks.update(t for t in n.split() if len(t) >= 3)
    return sorted(toks, key=len, reverse=True)


def redact(text, customer_name, agent_tokens):
    """Remove the customer's own name and any agent name/first name from free text so the reviewer sees no personal names.
    Also masks e-mail addresses and phone-like digit runs."""
    t = "" if text is None or text != text else str(text)
    toks = []
    if isinstance(customer_name, str) and customer_name.strip():
        toks = [customer_name.strip()] + [x for x in customer_name.split() if len(x) >= 3]
    for tok in sorted(set(toks), key=len, reverse=True):
        t = re.sub(r"\b" + re.escape(tok) + r"\b", "[CUSTOMER]", t, flags=re.I)
    for tok in agent_tokens:
        t = re.sub(r"\b" + re.escape(tok) + r"\b", "[AGENT]", t, flags=re.I)
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL]", t)
    t = re.sub(r"(?<!\w)\+?\d[\d\s-]{8,}\d(?!\w)", "[PHONE]", t)
    return t


def _previously_used_ids(val_dir=ROOT / "validation"):
    ids = set()
    for f in ["dev_sample_labels_prefix.csv", "holdout_sample_labels.csv"]:
        p = Path(val_dir) / f
        if p.exists():
            ids |= set(pd.read_csv(p, usecols=["ticket_id"])["ticket_id"])
    return ids


def build_sample(c, exc, plan=SAMPLE_PLAN, seed=SEED, exclude=None, customers=None, agents=None):
    """Stratified, reproducible sample. Excludes tickets already used in the AI-labelled samples.
    'not_confirmed' rows are random refund tickets the rules did NOT flag (used to look for missed cases)."""
    exclude = _previously_used_ids() if exclude is None else exclude
    names = _agent_name_tokens(agents)
    cust = {} if customers is None else dict(zip(customers["customer_id"], customers["name"]))
    c = c.assign(customer_name=c["customer_id"].map(cust))
    r = c[c["has_refund"]].copy()
    cls = exc.set_index("ticket_id")["exception_class"]
    r["existing_prediction"] = r["ticket_id"].map(cls).fillna("not_confirmed")
    r = r[~r["ticket_id"].isin(exclude)]
    parts = []
    for k, n in plan.items():
        pool = r[r["existing_prediction"] == k]
        parts.append(pool.sample(n=min(n, len(pool)), random_state=seed))
    s = pd.concat(parts).sample(frac=1, random_state=seed)          # shuffle so order does not reveal the class
    # neutral context: other tickets on the same order_id (does not reveal the prediction)
    by_order = c[c["order_id"].notna()].groupby("order_id")
    def others(row):
        if pd.isna(row["order_id"]):
            return ""
        g = by_order.get_group(row["order_id"]) if row["order_id"] in by_order.groups else c.iloc[0:0]
        g = g[g["ticket_id"] != row["ticket_id"]]
        return "; ".join(f"{t} (refund={'Y' if h else 'N'}, replacement_issued={x})"
                         for t, h, x in zip(g["ticket_id"], g["has_refund"], g["replacement_issued"]))
    out = pd.DataFrame({
        "ticket_id": s["ticket_id"], "created_at": s["created_at"].dt.strftime("%Y-%m-%d %H:%M"),
        "order_id_basis": s["order_join"].map({"order_id": "quoted on ticket", "fallback_cust_sku": "inferred (customer+SKU)"}).fillna("none"),
        "product_name": s["product_name"],
        "refund_amount_inr": s["refund_amount_norm"], "refund_reason_code": s["refund_reason_code"],
        "replacement_issued": s["replacement_issued"], "agent_id": s["agent_id"],
        "other_tickets_same_order": s.apply(others, axis=1),
        "customer_message": [redact(m, n, names) for m, n in zip(s["customer_message"], s["customer_name"])],
        "agent_notes": [redact(m, n, names) for m, n in zip(s["agent_notes"], s["customer_name"])],
        "human_label": "", "human_confidence": "", "evidence_basis": "", "evidence_source": "", "reasoning": "", "policy_reference": "",
        "correct": "", "review_notes": "", "reviewer_type": "", "existing_prediction": s["existing_prediction"]})
    return out[COLUMNS].reset_index(drop=True)


def init_sheet(c, exc, path=REVIEW_CSV, force=False, customers=None, agents=None):
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists - refusing to overwrite a sheet that may contain review work.")
    path.parent.mkdir(parents=True, exist_ok=True)
    build_sample(c, exc, customers=customers, agents=agents).to_csv(path, index=False)
    return path


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def load(path=REVIEW_CSV):
    path = Path(path)
    if not path.exists():
        return None
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    return d.rename(columns={"prediction": "existing_prediction", "ai_or_rule_prediction": "existing_prediction"})


def summarize(path=REVIEW_CSV, target_n=40):
    """Return None if no labels are filled in yet (=> 'pending'); otherwise metrics on the labelled rows."""
    d = load(path)
    if d is None:
        return dict(status="missing", total_rows=0, reviewed=0)
    d["human_label"] = d["human_label"].str.strip().str.lower()
    lab = d[d["human_label"] != ""].copy()
    bad = lab[~lab["human_label"].isin(LABELS)]
    if len(lab) == 0:
        return dict(status="pending", total_rows=len(d), reviewed=0)
    lab = lab[lab["human_label"].isin(LABELS)]
    pred = lab["existing_prediction"].str.strip().str.lower()
    ok = pred == lab["human_label"]
    n = len(lab); k = int(ok.sum())
    pos_p, pos_h = pred.isin(POSITIVE), lab["human_label"].isin(POSITIVE)
    rt = lab["reviewer_type"].str.strip().str.lower()
    lo, hi = wilson(k, n)
    by_pred = pd.DataFrame({"prediction": pred, "ok": ok}).groupby("prediction")["ok"].agg(reviewed="size", correct="sum").reset_index()
    return dict(
        status="complete" if n >= target_n else "partial", total_rows=len(d), reviewed=n, target_n=target_n,
        invalid_labels=int(len(bad)), correct=k, incorrect=n - k, accuracy=k / n, error_rate=(n - k) / n,
        ci_low=lo, ci_high=hi,
        human_ambiguous=int((lab["human_label"] == "ambiguous").sum()),
        fp=int((pos_p & ~pos_h).sum()), fn=int((~pos_p & pos_h).sum()),
        tp=int((pos_p & pos_h).sum()), tn=int((~pos_p & ~pos_h).sum()),
        low_confidence=int((lab["human_confidence"].str.lower() == "low").sum()),
        independent_rows=int((rt == "independent").sum()), author_rows=int((rt == "author").sum()),
        untyped_rows=int((~rt.isin(REVIEWER_TYPES)).sum()),
        by_pred=by_pred,
        mismatches=lab.loc[~ok, ["ticket_id", "existing_prediction", "human_label"]].rename(columns={"existing_prediction": "prediction"}).reset_index(drop=True),
        ai_rows=int((rt == "ai_assistant").sum()), human_rows=int(rt.isin(["independent", "author"]).sum()),
        reviewer_kind=("ai" if (rt == "ai_assistant").all() else "human" if rt.isin(["independent", "author"]).all() else "mixed"),
        independent_complete=bool(n >= target_n and (rt == "independent").all()),
        label_dist={k: int((lab["human_label"] == k).sum()) for k in LABELS}, pred_dist={k: int((pred == k).sum()) for k in LABELS},
        ok_excl_human_ambiguous=(int(ok[lab["human_label"] != "ambiguous"].sum()), int((lab["human_label"] != "ambiguous").sum())))


def score_in_place(path=REVIEW_CSV):
    """Fill the `correct` column (Y/N) for rows that have a human_label. Never touches the human's other columns."""
    d = load(path)
    lab = d["human_label"].str.strip().str.lower()
    d.loc[lab != "", "correct"] = np.where(d.loc[lab != "", "existing_prediction"].str.lower() == lab[lab != ""], "Yes", "No")
    d.loc[lab == "", "correct"] = ""
    d.to_csv(path, index=False)
    return summarize(path)


RESOLUTION = {
    ("ambiguous", "not_confirmed"): "Keep production class. Ambiguous cases are excluded from every financial figure, so nothing is overstated. "
                                    "Candidate refinement (NOT applied; n too small and not separable by reason code): do not raise a cross-ticket flag when the refund text describes an unfulfilled order or a payment reversal.",
    ("not_confirmed", "ambiguous"): "Review queue: the rule missed a cross-ticket or text signal. Inspect before changing any rule.",
    ("likely", "confirmed"): "Review the flag/note conflict; do not change the rule from one case.",
    ("confirmed", "likely"): "Downgrade only if fulfilment evidence is missing; the rule is field-based by design.",
    ("likely", "ambiguous"): "Text may be a keyword false positive; add to the failure list.",
    ("not_confirmed", "likely"): "Possible false negative: add the phrasing to the failure list and test on a fresh sample.",
    ("not_confirmed", "confirmed"): "Possible false negative: investigate the missing signal.",
}


def write_disagreements(path=REVIEW_CSV, out=ROOT / "validation" / "review_disagreements.csv"):
    """One row per case where the reviewer's label differs from the existing class. Reasons come from the review sheet's own columns;
    no customer message or agent note text is copied."""
    d = load(path)
    d = d[d["human_label"].str.strip() != ""]
    x = d[d["existing_prediction"].str.lower() != d["human_label"].str.lower()].copy()
    x["recommended_resolution"] = [RESOLUTION.get((a.lower(), b.lower()), "Review case manually.") for a, b in zip(x["existing_prediction"], x["human_label"])]
    x = x.rename(columns={"reasoning": "reason_for_disagreement", "evidence_basis": "evidence"})
    x[["ticket_id", "existing_prediction", "human_label", "reason_for_disagreement", "evidence", "recommended_resolution"]].to_csv(out, index=False)
    return out


def write_public_summary(path=REVIEW_CSV, out=ROOT / "validation" / "review_summary.csv"):
    """Aggregate counts only - no ticket ids, free text, names or other identifiers."""
    s = summarize(path)
    if s.get("reviewed", 0) == 0:
        return None
    ld, pdist = s["label_dist"], s["pred_dist"]
    both_amb = int(((load(path)["existing_prediction"].str.lower() == "ambiguous") & (load(path)["human_label"].str.lower() == "ambiguous")).sum())
    row = dict(sample_size=s["reviewed"], correct_count=s["correct"], incorrect_count=s["incorrect"], ambiguous_count=ld["ambiguous"],
               accuracy=round(s["accuracy"], 4), error_rate=round(s["error_rate"], 4), false_positive_count=s["fp"], false_negative_count=s["fn"],
               confirmed_count=ld["confirmed"], likely_count=ld["likely"],
               ambiguous_distribution=f"existing={pdist['ambiguous']};reviewer={ld['ambiguous']};both={both_amb}",
               not_confirmed_count=ld["not_confirmed"], reviewer_type=("ai_assistant" if s["reviewer_kind"] == "ai" else s["reviewer_kind"]))
    pd.DataFrame([row]).to_csv(out, index=False)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true"); ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    if a.init:
        from . import pipeline
        res = pipeline.run(write=False)
        print("wrote", init_sheet(res["canonical"], res["exceptions"], customers=res["raw"]["customers"], agents=res["raw"]["agents"]))
    if a.score or not a.init:
        s = score_in_place() if a.score else summarize()
        print({k: v for k, v in s.items() if k not in ("by_pred", "mismatches")})

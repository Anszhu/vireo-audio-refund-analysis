"""Independent validation layer. Uses the csv module (not pandas) to recompute key numbers."""
import csv
import re
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CODES = {"GW-OTHER", "DOA-REPL", "LOST-TRANSIT", "DUP-PAYMENT", "CANCEL", "PRICE-ADJ", "RETURN-QC-OK", "WTY-BUYBACK"}


def independent_totals(raw_dir):
    """Re-derive de-duplicated, unit-normalised refund totals without using the pipeline code."""
    rows = list(csv.DictReader(open(Path(raw_dir) / "tickets.csv", newline="", encoding="utf-8")))
    by_id = defaultdict(list)
    for r in rows:
        by_id[r["ticket_id"]].append(r)
    total_raw = sum(float(r["refund_amount_inr"]) for r in rows if r["refund_amount_inr"])
    total, n, per_month = 0.0, 0, defaultdict(float)
    for tid, rs in by_id.items():
        hd = [r for r in rs if r["source_system"] == "helpdesk"]
        r = hd[0] if hd else rs[0]
        if r["refund_amount_inr"]:
            v = float(r["refund_amount_inr"]) / (100 if r["source_system"] == "legacy_fd" else 1)
            total += v; n += 1; per_month[r["created_at"][:7]] += v
    return dict(rows=len(rows), unique_ids=len(by_id), raw_total=total_raw, canon_total=total,
                canon_count=n, per_month=dict(per_month))


def automated_checks(res, raw_dir):
    c, raw, parsed = res["canonical"], res["raw"], res["parsed"]
    ind = independent_totals(raw_dir)
    out = []
    def chk(name, ok, detail=""):
        out.append(dict(check=name, passed=bool(ok), detail=detail))
    chk("Row count: raw rows = canonical rows + dropped re-import rows",
        len(raw["tickets"]) == len(c) + len(res["dropped"]), f"{len(raw['tickets'])} = {len(c)} + {len(res['dropped'])}")
    chk("Canonical ticket_id unique", c["ticket_id"].is_unique)
    chk("Only re-import pairs dropped (each dropped id also kept)", res["dropped"]["ticket_id"].isin(c["ticket_id"]).all())
    chk("Dropped rows are all legacy_fd copies", (res["dropped"]["source_system"] == "legacy_fd").all())
    chk("Unique ticket count matches independent csv count", c["ticket_id"].nunique() == ind["unique_ids"])
    chk("Canonical refund total = independent recomputation",
        abs(c["refund_amount_norm"].sum() - ind["canon_total"]) < 0.01,
        f"pipeline {c['refund_amount_norm'].sum():,.0f} vs independent {ind['canon_total']:,.0f}")
    chk("Canonical refund count = independent recomputation", int(c["has_refund"].sum()) == ind["canon_count"])
    pm = c[c.has_refund].groupby("month")["refund_amount_norm"].sum()
    chk("Monthly totals = independent recomputation",
        all(abs(pm.get(m, 0) - v) < 0.01 for m, v in ind["per_month"].items()) and len(pm) == len(ind["per_month"]))
    chk("Raw export total = independent raw sum", abs(res["recon"].iloc[0]["refund_value_inr"] - ind["raw_total"]) < 0.01)
    b = res["bridge"]
    chk("Quarterly bridge: raw - dupes - scaling = canonical",
        np.allclose(b["raw_export_value"] + b["less_reimport_duplicates_value"] + b["less_legacy_unit_scaling_value"],
                    b["canonical_value"]))
    chk("Reason totals sum to canonical total", abs(res["reasons"]["refund_value"].sum() - c["refund_amount_norm"].sum()) < 0.01)
    chk("Agent monthly refund_value sums to canonical total",
        abs(res["agent_monthly"]["refund_value"].sum() - c["refund_amount_norm"].sum()) < 0.01)
    chk("Agent monthly refund_count sums to canonical count", int(res["agent_monthly"]["refund_count"].sum()) == int(c["has_refund"].sum()))
    chk("Refund amount and reason code are null together", c["refund_amount_raw"].isna().equals(c["refund_reason_code"].isna()))
    chk("All reason codes are in the policy list", set(c["refund_reason_code"].dropna()) <= CODES)
    chk("All refund amounts positive", (c.loc[c.has_refund, "refund_amount_norm"] > 0).all())
    chk("Every agent_id found in roster in assignment window", (c["roster_match"] == "in_window").all())
    chk("Order-id join: customer_id agrees with orders.csv", not c["order_cust_mismatch"].any())
    chk("Order-id join: SKU agrees with orders.csv", not c["order_sku_mismatch"].any())
    chk("Every ticket SKU found in products.csv", c["family"].notna().all())
    chk("Every customer_id found in customers.csv", c["care_plus"].notna().all())
    chk("Legacy amounts scaled, helpdesk unscaled",
        (c.loc[c.source_system == "legacy_fd", "scale_divisor"] == 100).all() and (c.loc[c.source_system == "helpdesk", "scale_divisor"] == 1).all())
    chk("Refund / retail price plausible after scaling (max ratio <= 2.0)",
        (c.loc[c.has_refund, "refund_amount_norm"] / c.loc[c.has_refund, "retail_price_inr"]).max() <= 2.0 + 1e-9)
    ex = res["exceptions"]
    conf = ex[ex.exception_class == "confirmed"]
    chk("Confirmed exceptions all have refund>0 and replacement_issued=Y", (conf["refund_amount_norm"] > 0).all() and (conf["replacement_issued"] == "Y").all())
    chk("Exception ids are unique", ex["ticket_id"].is_unique)
    chk("Refunds on non-refund-coded tickets: none", not (c["refund_reason_code"].notna() & ~c["has_refund"]).any())
    return out


def note_amount_agreement(c):
    """Informational: does the Rs amount typed in agent_notes equal the refund field?"""
    pat = re.compile(r"(?:rs\.?\s*|\()(\d{2,6})\)?", re.I)
    hit = agree = 0
    for n, a in zip(c.loc[c.has_refund, "agent_notes"], c.loc[c.has_refund, "refund_amount_norm"]):
        m = pat.findall(str(n))
        if m:
            hit += 1
            agree += int(any(abs(int(x) - a) < 1 for x in m))
    return hit, agree


def manual_metrics(val_dir=ROOT / "validation"):
    out = {}
    for name, f in [("dev", "dev_sample_labels_prefix.csv"), ("holdout", "holdout_sample_labels.csv")]:
        d = pd.read_csv(Path(val_dir) / f).fillna({"note": ""})
        pipe = d["pipeline_exception_class_prefix" if name == "dev" else "pipeline_exception_class_at_review"]
        man = d["reviewer_exception_class"]
        pos = lambda s: s.isin(["confirmed", "likely"])
        tp = int((pos(pipe) & pos(man)).sum()); fp = int((pos(pipe) & ~pos(man)).sum()); fn = int((~pos(pipe) & pos(man)).sum())
        tn = int((~pos(pipe) & ~pos(man)).sum())
        ex_rows = d[d.sample_group.str.startswith("exc_")]
        cls_ok = int((ex_rows["pipeline_exception_class_prefix" if name == "dev" else "pipeline_exception_class_at_review"] == ex_rows["reviewer_exception_class"]).sum())
        t = d[~d.sample_group.str.startswith("exc_")]
        ai = t["ai_topic_at_review"]; mt = t["reviewer_topic"]
        answered = ai != "unknown"
        correct = int(((ai == mt) & answered).sum()); wrong = int(((ai != mt) & answered).sum())
        abst = int((~answered).sum())
        nf = d[~d.sample_group.str.startswith("exc_")]          # random refunds NOT selected because they were flagged
        out[name] = dict(n=len(d), tp=tp, fp=fp, fn=fn, tn=tn,
                         nonflag_n=len(nf), nonflag_missed=int(nf["reviewer_exception_class"].isin(["confirmed", "likely"]).sum()),
                         precision=tp / (tp + fp) if tp + fp else float("nan"),
                         recall=tp / (tp + fn) if tp + fn else float("nan"),
                         exc_rows=len(ex_rows), exc_class_correct=cls_ok,
                         topic_n=len(t), topic_correct=correct, topic_wrong=wrong, topic_abstain=abst)
    return out

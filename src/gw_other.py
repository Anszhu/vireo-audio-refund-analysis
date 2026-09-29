"""GW-OTHER 'requires review' metrics.

Policy s5: goodwill credits are capped at Rs 500 per ticket and need Team Lead approval. GW-OTHER is the first
dropdown option, so it also holds refunds that are not goodwill at all. A GW-OTHER refund above Rs 500 therefore
*requires review* - it may be a cap/approval breach OR a mis-coded ordinary refund. The data cannot tell which,
and nothing here is a finding of misconduct.
"""
import pandas as pd

CAP = 500


def gw_review_metrics(c, cap=CAP):
    r = c[c["has_refund"]]
    gw = r[r["refund_reason_code"] == "GW-OTHER"]
    over = gw[gw["refund_amount_norm"] > cap]
    tot_val = r["refund_amount_norm"].sum()
    text_specific = over["ai_gw_specific_reason"].fillna(False).astype(bool)
    text_goodwill = over["ai_topic"].eq("goodwill")
    m = dict(gw_refunds=int(len(gw)), gw_value=float(gw["refund_amount_norm"].sum()),
             gw_pct_of_total_value=float(100 * gw["refund_amount_norm"].sum() / tot_val),
             cap=cap, gw_over_cap=int(len(over)), gw_over_cap_value=float(over["refund_amount_norm"].sum()),
             gw_over_cap_pct_of_gw=float(100 * len(over) / len(gw)),
             gw_over_cap_pct_of_total_value=float(100 * over["refund_amount_norm"].sum() / tot_val),
             over_cap_text_names_other_reason=int(text_specific.sum()),
             over_cap_text_says_goodwill=int(text_goodwill.sum()),
             over_cap_text_uninformative=int((over["ai_topic"] == "unknown").sum()))
    return m


def gw_review_table(c, cap=CAP):
    """Long table for outputs/gw_other_review.csv: headline metrics + text-derived categories."""
    m = gw_review_metrics(c, cap)
    rows = [("headline", "GW-OTHER refunds (count)", m["gw_refunds"]),
            ("headline", "GW-OTHER refund value (INR)", round(m["gw_value"], 2)),
            ("headline", "GW-OTHER % of total canonical refund value", round(m["gw_pct_of_total_value"], 2)),
            ("headline", f"GW-OTHER refunds above Rs {cap} (count) - requires review", m["gw_over_cap"]),
            ("headline", f"GW-OTHER refunds above Rs {cap} (% of GW-OTHER refunds)", round(m["gw_over_cap_pct_of_gw"], 2)),
            ("headline", f"GW-OTHER refunds above Rs {cap} (value, INR)", round(m["gw_over_cap_value"], 2)),
            ("headline", f"GW-OTHER above Rs {cap}: % of total canonical refund value", round(m["gw_over_cap_pct_of_total_value"], 2)),
            ("over_cap_text_signal", "note/message names a specific non-goodwill reason (possible mis-coding)", m["over_cap_text_names_other_reason"]),
            ("over_cap_text_signal", "text itself says goodwill/gesture", m["over_cap_text_says_goodwill"]),
            ("over_cap_text_signal", "text uninformative (topic unknown)", m["over_cap_text_uninformative"])]
    r = c[c["has_refund"] & (c["refund_reason_code"] == "GW-OTHER")]
    for topic, g in r.groupby("ai_topic"):
        o = g[g["refund_amount_norm"] > cap]
        rows.append(("text_derived_category_all_gw_other", topic, len(g)))
        rows.append(("text_derived_category_above_cap", topic, len(o)))
    t = pd.DataFrame(rows, columns=["section", "metric", "value"])
    t["note"] = ("Requires review - not proof of mis-coding or misconduct; text categories come from deterministic rules "
                 "and are QA prompts, not a source of record")
    return t

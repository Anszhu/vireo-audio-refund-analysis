"""Refund reconciliation: raw export -> dedupe -> unit normalisation -> canonical."""
import numpy as np
import pandas as pd


def scale_evidence(raw_parsed, canonical, products):
    """Data evidence for the legacy unit (no assumption): (a) exact x100 on re-import pairs,
    (b) refund / retail price ratio by source system."""
    t = raw_parsed
    both = t[t["ticket_id"].isin(t.loc[t["in_reimport_pair"], "ticket_id"])] if "in_reimport_pair" in t else t
    ids = t.groupby("ticket_id")["source_system"].nunique()
    ids = ids[ids > 1].index
    p = t[t.ticket_id.isin(ids) & t.refund_amount_raw.notna()].pivot_table(
        index="ticket_id", columns="source_system", values="refund_amount_raw", aggfunc="first")
    exact100 = float((p["legacy_fd"] == p["helpdesk"] * 100).mean()) if len(p) else float("nan")
    r = t[t.refund_amount_raw.notna()].merge(products[["sku", "retail_price_inr"]],
                                             left_on="product_sku", right_on="sku", how="left")
    r["ratio"] = r["refund_amount_raw"] / r["retail_price_inr"]
    med = r.groupby("source_system")["ratio"].median()
    return dict(pairs_with_refund=int(len(p)), pairs_exact_x100=exact100,
                median_refund_to_retail_helpdesk=float(med.get("helpdesk", np.nan)),
                median_refund_to_retail_legacy=float(med.get("legacy_fd", np.nan)))


def bridge(raw_parsed, canonical):
    """Quarter-by-quarter bridge:
    raw export -> less re-import duplicates -> less legacy unit scaling -> canonical."""
    t = raw_parsed.copy()
    t["quarter"] = t["created_at"].dt.to_period("Q").astype(str)
    raw = t.groupby("quarter")["refund_amount_raw"].agg(count="count", value="sum")
    # duplicates removed = rows dropped by dedupe (legacy copies of re-imported ids), at RAW value
    kept_ids = canonical[["ticket_id", "source_system"]]
    m = t.merge(kept_ids.assign(_k=1), on=["ticket_id", "source_system"], how="left")
    dropped = m[m["_k"].isna()]
    dup = dropped.groupby("quarter")["refund_amount_raw"].agg(count="count", value="sum")
    after_dedupe_raw = m[m["_k"].notna()].groupby("quarter")["refund_amount_raw"].agg(count="count", value="sum")
    canon = canonical.groupby("quarter")["refund_amount_norm"].agg(count="count", value="sum")
    q = pd.DataFrame({
        "raw_export_count": raw["count"], "raw_export_value": raw["value"],
        "less_reimport_duplicates_value": -dup["value"].reindex(raw.index).fillna(0),
        "after_dedupe_raw_units_value": after_dedupe_raw["value"],
        "canonical_count": canon["count"], "canonical_value": canon["value"]}).fillna(0)
    q["less_legacy_unit_scaling_value"] = q["canonical_value"] - q["after_dedupe_raw_units_value"]
    q["duplicate_refund_rows_removed"] = dup["count"].reindex(q.index).fillna(0).astype(int)
    return q.reset_index()


def source_split(raw_parsed, canonical):
    raw = raw_parsed.groupby("source_system")["refund_amount_raw"].agg(rows="size", refund_rows="count", raw_value="sum")
    can = canonical.groupby("source_system")["refund_amount_norm"].agg(refund_rows_canonical="count", canonical_value="sum")
    return raw.join(can, how="outer").fillna(0).reset_index()


def reconciliation_table(raw_parsed, canonical, dropped):
    """Long-format table written to outputs/refund_reconciliation.csv"""
    rows = []
    def add(section, period, item, cnt, val, note=""):
        rows.append(dict(section=section, period=period, item=item, refund_count=cnt,
                         refund_value_inr=None if val is None else round(float(val), 2), note=note))
    rt = raw_parsed["refund_amount_raw"]
    add("A_total_bridge", "all", "1. Raw export (as exported, mixed units)", int(rt.notna().sum()), rt.sum(),
        "Sum of refund_amount_inr over all 12,238 exported rows; legacy_fd in paise, helpdesk in rupees")
    dv = dropped["refund_amount_raw"]
    add("A_total_bridge", "all", "2. Less re-imported duplicate rows (legacy copy, raw units)", -int(dv.notna().sum()), -dv.sum(),
        "638 ticket_ids exported under both systems; helpdesk copy kept")
    kept_raw = canonical["refund_amount_raw"]
    add("A_total_bridge", "all", "3. After de-duplication, still mixed units", int(kept_raw.notna().sum()), kept_raw.sum())
    scale = canonical["refund_amount_norm"].sum() - kept_raw.sum()
    add("A_total_bridge", "all", "4. Less legacy unit scaling (legacy_fd / 100)", 0, scale,
        "Evidence: legacy amounts are exactly 100x helpdesk amounts on every re-imported pair with a refund")
    add("A_total_bridge", "all", "5. Canonical refund total (rupees)", int(canonical["has_refund"].sum()), canonical["refund_amount_norm"].sum())
    b = bridge(raw_parsed, canonical)
    for _, r in b.iterrows():
        add("B_quarterly_bridge", r["quarter"], "raw export value", int(r["raw_export_count"]), r["raw_export_value"])
        add("B_quarterly_bridge", r["quarter"], "less re-import duplicates", -int(r["duplicate_refund_rows_removed"]), r["less_reimport_duplicates_value"])
        add("B_quarterly_bridge", r["quarter"], "less legacy unit scaling", 0, r["less_legacy_unit_scaling_value"])
        add("B_quarterly_bridge", r["quarter"], "canonical value", int(r["canonical_count"]), r["canonical_value"])
    for s, g in canonical.groupby("source_system"):
        add("C_source_system_canonical", "all", s, int(g["has_refund"].sum()), g["refund_amount_norm"].sum())
    for m, g in canonical.groupby("month"):
        add("D_monthly_canonical", m, "all reasons", int(g["has_refund"].sum()), g["refund_amount_norm"].sum())
    for q, g in canonical.groupby("quarter"):
        add("E_quarterly_canonical", q, "all reasons", int(g["has_refund"].sum()), g["refund_amount_norm"].sum())
    for c, g in canonical[canonical.has_refund].groupby("refund_reason_code"):
        add("F_reason_canonical", "all", c, len(g), g["refund_amount_norm"].sum())
    for a, g in canonical[canonical.has_refund].groupby("agent_id"):
        add("G_agent_canonical", "all", str(a), len(g), g["refund_amount_norm"].sum())
    return pd.DataFrame(rows)


def clean_bridge(b):
    """One tidy table: per quarter and in total, raw export -> less duplicates -> less legacy paise scaling -> canonical (INR).
    Order of the bridge: duplicates first, then unit scaling of what remains (the split between the two depends on that order;
    the canonical total does not)."""
    t = b.rename(columns={"raw_export_value": "raw_export_inr", "less_reimport_duplicates_value": "less_reimport_duplicates_inr",
                          "less_legacy_unit_scaling_value": "less_legacy_paise_scaling_inr", "canonical_value": "canonical_inr",
                          "raw_export_count": "raw_refund_rows", "duplicate_refund_rows_removed": "duplicate_refund_rows_removed",
                          "canonical_count": "canonical_refund_rows"})
    cols = ["quarter", "raw_refund_rows", "raw_export_inr", "duplicate_refund_rows_removed", "less_reimport_duplicates_inr",
            "less_legacy_paise_scaling_inr", "canonical_refund_rows", "canonical_inr"]
    t = t[cols].copy()
    tot = t.drop(columns="quarter").sum(); tot["quarter"] = "TOTAL"
    t = pd.concat([t, pd.DataFrame([tot])[cols]], ignore_index=True)
    t["bridge_check_inr"] = (t["raw_export_inr"] + t["less_reimport_duplicates_inr"] + t["less_legacy_paise_scaling_inr"] - t["canonical_inr"]).round(2)
    for c_ in ["raw_export_inr", "less_reimport_duplicates_inr", "less_legacy_paise_scaling_inr", "canonical_inr"]:
        t[c_] = t[c_].round(2)
    return t

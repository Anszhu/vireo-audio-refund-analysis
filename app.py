"""Vireo Audio - Support Refund Analysis (Streamlit).   Run:  streamlit run app.py"""
import sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from src import pipeline, validate, human_review, agent_analysis as aa, refund_analysis as ra  # noqa: E402
from src.ingest import RAW_DIR  # noqa: E402

st.set_page_config(page_title="Vireo refund analysis", layout="wide")


@st.cache_data(show_spinner="Running pipeline on data/raw ...")
def load():
    res = pipeline.run(write=False)
    return res


def inr(x):
    return f"₹{x:,.0f}"


def lakh(x):
    return f"₹{x/1e5:,.2f} L"


if not (Path(RAW_DIR) / "tickets.csv").exists():
    st.error("Input files not found. Place the five CSVs in data/raw/ (see data/README.md).")
    st.stop()

res = load()
c, ex, b = res["canonical"], res["exceptions"], res["business"]
r = c[c.has_refund]

page = st.sidebar.radio("Page", ["1 Executive summary", "2 Refund explorer", "3 Agent analysis",
                                 "4 Exception review", "5 Data quality & reconciliation", "6 Board Pack"])
st.sidebar.caption("Months use ticket created_at (IST). Money = canonical rupees (legacy ÷ 100, re-imports removed).")

if page.startswith("1"):
    st.title("Executive summary")
    raw_total = res["recon"].iloc[0]["refund_value_inr"]
    a, b1, c1, d = st.columns(4)
    a.metric("Refund total (canonical)", lakh(r.refund_amount_norm.sum()))
    b1.metric("Refund tickets", f"{len(r):,}")
    c1.metric("Avg per quarter (6 qtrs)", lakh(r.refund_amount_norm.sum() / 6))
    d.metric("Raw export said", f"₹{raw_total/1e7:,.1f} crore", help="Mixed paise/rupees + duplicate re-imports")
    e = ex.exception_class.value_counts()
    st.info(f"**Fact:** {b['confirmed_tickets']} of {b['refund_tickets']:,} refund tickets ({b['current_rate']:.1%}, last 3 quarters) carry both a refund and a replacement "
            f"(policy §5 exception). **Illustrative {b['target_rate']:.0%} target scenario (planning assumption, not a forecast):** ≈ **{inr(b['avoidable_per_quarter'])} per quarter** "
            f"of avoided replacement cost. Exceptions: {e.get('confirmed',0)} confirmed, {e.get('likely',0)} likely, {e.get('ambiguous',0)} ambiguous.")
    m = res["monthly"]
    st.plotly_chart(px.bar(m, x="month", y="refund_value", title="Monthly refund value (₹)"))
    c2, c3 = st.columns(2)
    c2.plotly_chart(px.bar(res["quarterly"], x="quarter", y="refund_value", title="Quarterly refund value (₹)"))
    rs = res["reasons"]
    c3.plotly_chart(px.pie(rs, names="refund_reason_code", values="refund_value", title="Value by reason code"))
    st.subheader("Reason codes")
    st.dataframe(rs.round(1), hide_index=True)
    st.caption("GW-OTHER is the first dropdown option; text on most of its tickets names a specific reason (see Exception review).")

elif page.startswith("2"):
    st.title("Refund explorer")
    f = r.copy()
    col = st.columns(6)
    sel = lambda lab, colname, i: col[i].multiselect(lab, sorted(f[colname].dropna().unique()))
    fm, fr, ft, fti, fa, fs = sel("Month", "month", 0), sel("Reason", "refund_reason_code", 1), sel("Team", "agent_team", 2), \
        sel("Tier", "agent_tier", 3), sel("Agent", "agent_name", 4), sel("Source", "source_system", 5)
    fch = st.multiselect("Order channel", sorted(f["order_channel"].dropna().unique()))
    for colname, v in [("month", fm), ("refund_reason_code", fr), ("agent_team", ft), ("agent_tier", fti),
                       ("agent_name", fa), ("source_system", fs), ("order_channel", fch)]:
        if v:
            f = f[f[colname].isin(v)]
    x, y, z = st.columns(3)
    x.metric("Refund count", f"{len(f):,}"); y.metric("Refund value", inr(f.refund_amount_norm.sum()))
    z.metric("Average refund", inr(f.refund_amount_norm.mean()) if len(f) else "–")
    if len(f):
        st.plotly_chart(px.bar(f.groupby(["month", "refund_reason_code"], as_index=False).refund_amount_norm.sum(),
                               x="month", y="refund_amount_norm", color="refund_reason_code"))
    st.dataframe(f[["ticket_id", "created_at", "refund_amount_norm", "refund_amount_raw", "refund_reason_code", "replacement_issued",
                    "agent_name", "agent_team", "agent_tier", "product_name", "order_channel", "source_system", "agent_notes"]],
                 hide_index=True)

elif page.startswith("3"):
    st.title("Agent analysis")
    st.warning("Agents are compared **only within their own team**. Returns Desk and Billing are refund-handling teams by design, "
               "and Tier 2 (Escalations & Warranty) is multi-touch work that policy says must not be compared with Tier 1 on volume.")
    st.subheader("Team / tier context")
    t = res["team"].copy()
    st.dataframe(t.round({"refund_value": 0, "avg_refund": 0, "refund_rate": 3, "share_of_refund_value": 3}),
                 hide_index=True)
    at = res["agent_totals"]
    team = st.selectbox("Team", sorted(at.team.unique()))
    x = at[at.team == team].sort_values("agent_id")   # neutral order: not a ranking
    st.dataframe(x[["agent_id", "agent_name", "site", "tier", "attended", "refund_count", "refund_value", "refund_rate", "team_rate",
                    "avg_refund", "value_per_ticket", "z_vs_team"]].round(3), hide_index=True)
    st.caption(f"z_vs_team = agent's refund rate vs own team's rate in standard errors. Agents beyond ±3: {int(at.outside_normal_range_for_team.sum())}. "
               "**Anomaly-review signal, not an agent performance ranking** - a high value is a prompt to look, not evidence of poor performance. Agents are listed by id, not by refund rate.")
    st.plotly_chart(px.scatter(x, x="attended", y="refund_rate", hover_name="agent_name", size="refund_count",
                               title=f"{team}: refund rate vs tickets handled"))
    st.subheader("Monthly agent table")
    st.dataframe(res["agent_monthly"].round(3), hide_index=True)

elif page.startswith("4"):
    st.title("Exception review")
    st.write("**confirmed** = refund amount and replacement_issued=Y on the same ticket · **likely** = note says both remedies given but flag is N (text only) · "
             "**ambiguous** = contradictory/unclear, or another ticket on the same order carries a replacement.")
    c1_, c2_ = st.columns(2)
    cls = c1_.multiselect("Confidence", ["confirmed", "likely", "ambiguous"], default=["confirmed", "likely"])
    srcs = c2_.multiselect("Evidence source", sorted(ex.evidence_source.unique()))
    f = ex[ex.exception_class.isin(cls)]
    if srcs:
        f = f[f.evidence_source.isin(srcs)]
    st.metric("Cases", len(f))
    ev_cols = ["ticket_id", "customer_id", "order_id", "refund_amount_norm", "refund_reason_code", "replacement_issued", "agent_id", "agent_name",
               "created_at", "classification", "confidence", "evidence", "evidence_source", "order_id_basis"]
    st.dataframe(f[ev_cols], hide_index=True)
    st.caption("Confidence is never upgraded: *Likely* is the agent's own note only; *Ambiguous* stays ambiguous. The customer message is supporting context "
               "and is not used to classify. Order ids marked 'inferred (customer+SKU)' are a pipeline guess, not quoted by the customer.")
    with st.expander("Evidence text (customer message and agent note)"):
        pick = st.selectbox("Ticket", f.ticket_id.tolist()) if len(f) else None
        if pick:
            z = f[f.ticket_id == pick].iloc[0]
            st.write("**Evidence source:**", z.evidence_source); st.write("**Customer:**", z.customer_message); st.write("**Agent note:**", z.agent_notes)
    st.subheader("GW-OTHER requiring review")
    g = res["gw_metrics"]
    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric("GW-OTHER refunds", f"{g['gw_refunds']:,}"); g2.metric("Total value", lakh(g["gw_value"]))
    g3.metric("% of total refund value", f"{g['gw_pct_of_total_value']:.1f}%")
    g4.metric(f"Above ₹{g['cap']}", f"{g['gw_over_cap']:,}"); g5.metric(f"% above ₹{g['cap']}", f"{g['gw_over_cap_pct_of_gw']:.1f}%")
    st.caption(f"Policy §5 caps goodwill credits at ₹{g['cap']} with Team Lead approval. GW-OTHER is the first dropdown option, so above-cap refunds are either a cap/approval issue "
               f"or ordinary refunds coded as GW-OTHER - the data cannot tell which. Of the {g['gw_over_cap']:,} above cap, {g['over_cap_text_names_other_reason']:,} name a specific "
               f"ordinary reason in the text and {g['over_cap_text_says_goodwill']:,} describe goodwill. **Requires review; not evidence of misconduct.**")
    gt = res["gw_table"]
    st.dataframe(gt[gt.section.str.startswith("text_derived")].pivot_table(index="metric", columns="section", values="value", aggfunc="sum")
                 .rename(columns={"text_derived_category_all_gw_other": "all GW-OTHER", "text_derived_category_above_cap": f"above ₹{g['cap']}"}))
    st.subheader("AI-flagged reason-code review (recorded code stays the source of record)")
    gw = r[r.ai_gw_specific_reason]
    st.write(f"{len(gw):,} of {int((r.refund_reason_code=='GW-OTHER').sum()):,} GW-OTHER refunds have text naming a specific reason; "
             f"{int(r.ai_code_mismatch.sum())} non-GW refunds have a code that disagrees with the text.")
    st.dataframe(r[r.ai_gw_specific_reason | r.ai_code_mismatch][["ticket_id", "refund_reason_code", "ai_topic", "ai_suggested_codes",
                 "refund_amount_norm", "agent_name", "agent_notes"]], hide_index=True)

elif page.startswith("6"):
    st.title("Board Pack - refunds")
    checks = validate.automated_checks(res, RAW_DIR)
    ok = all(x["passed"] for x in checks)
    q = res["quarterly"].set_index("quarter")
    bc = res["bridge_clean"]; tot = bc[bc.quarter == "TOTAL"].iloc[0]
    canon = r.refund_amount_norm.sum()

    st.subheader("1. Refund position")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Raw exported total", f"₹{tot.raw_export_inr/1e7:,.2f} crore", help="As exported: legacy in paise, helpdesk in rupees, re-imported tickets counted twice")
    p2.metric("Canonical total", lakh(canon), help=f"{len(r):,} refund tickets, Jan 2025 - Jun 2026")
    p3.metric("Quarterly average", lakh(canon / len(q)), help=f"{len(q)} quarters")
    p4.metric(f"Latest quarter ({q.index[-1]})", lakh(q.refund_value.iloc[-1]))

    st.subheader("2. Reconciliation: raw → canonical")
    st.dataframe(pd.DataFrame([
        ("Raw export (mixed units)", f"₹{tot.raw_export_inr/1e7:,.2f} crore"),
        (f"Less re-import duplicates ({int(tot.duplicate_refund_rows_removed)} refund rows)", f"−₹{-tot.less_reimport_duplicates_inr/1e7:,.2f} crore"),
        ("Less legacy paise scaling (legacy ÷ 100)", f"−₹{-tot.less_legacy_paise_scaling_inr/1e7:,.2f} crore"),
        ("Canonical total", f"₹{tot.canonical_inr/1e5:,.2f} lakh")], columns=["Step", "Value"]), hide_index=True)
    if ok:
        st.success(f"Reconciled to the rupee; {len(checks)}/{len(checks)} checks pass. Legacy paise is the dominant factor; duplicates are secondary "
                   "(the split depends on bridge order - see page 5). The helpdesk's ≈₹11 lakh/quarter is consistent with the canonical average.")
    else:
        st.error("Not reconciled: at least one automated check fails - see page 5.")

    st.subheader("3. Refund drivers")
    rs = res["reasons"][["refund_reason_code", "refund_count", "refund_value", "pct_of_value"]].copy()
    rs["refund_value"] = rs["refund_value"].map(inr); rs["pct_of_value"] = rs["pct_of_value"].map(lambda v: f"{v:.1f}%")
    st.dataframe(rs.rename(columns={"refund_reason_code": "Reason code", "refund_count": "Refunds", "refund_value": "Value", "pct_of_value": "% of value"}), hide_index=True)

    st.subheader("4. Control issues")
    ec = ex.exception_class.value_counts()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Refund + replacement flagged", f"{len(ex):,}"); k2.metric("Confirmed", f"{ec.get('confirmed', 0):,}", help="Refund amount and replacement_issued=Y on the same ticket")
    k3.metric("Likely", f"{ec.get('likely', 0):,}", help="Agent note says both were given; flag is N (text only)")
    k4.metric("Ambiguous", f"{ec.get('ambiguous', 0):,}", help="Evidence conflicts or is unclear; not counted as a violation")
    g = res["gw_metrics"]
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("GW-OTHER refunds", f"{g['gw_refunds']:,}", help=f"Total value {lakh(g['gw_value'])} = {g['gw_pct_of_total_value']:.1f}% of canonical value")
    g2.metric(f"Above ₹{g['cap']} cap", f"{g['gw_over_cap']:,}"); g3.metric(f"% above ₹{g['cap']}", f"{g['gw_over_cap_pct_of_gw']:.1f}%")
    g4.metric("Value of above-cap subset", lakh(g["gw_over_cap_value"]), help=f"{g['gw_over_cap_pct_of_total_value']:.1f}% of canonical refund value")
    st.caption("GW-OTHER requires review - a cap/approval issue or ordinary refunds coded to the first dropdown option; the data cannot tell which. Not evidence of misconduct.")

    st.subheader("5. Business opportunity")
    st.write(f"**Observed:** {b['confirmed_tickets']} of {b['refund_tickets']:,} refund tickets ({b['current_rate']:.1%}, last 3 quarters) are confirmed refund + replacement; "
             f"replacement cost ≈ {inr(b['confirmed_replacement_cost_per_quarter'])} per quarter.")
    st.write(f"**Illustrative {b['target_rate']:.0%} target scenario - planning assumption, not a forecast:** ≈ **{inr(b['avoidable_per_quarter'])} per quarter** avoided "
             f"(range {inr(res['sensitivity'].query('basis == \"PLANNING ASSUMPTION\"').avoidable_replacement_cost_per_quarter_inr.min())} to "
             f"{inr(res['sensitivity'].query('basis == \"PLANNING ASSUMPTION\"').avoidable_replacement_cost_per_quarter_inr.max())} for residual 5% to 0%).")

    st.subheader("6. Management actions")
    st.markdown("1. Use the canonical totals; have IT confirm the paise unit and remove the re-import.\n"
                "2. Review the confirmed refund + replacement cases with Team Leads.\n"
                "3. Review GW-OTHER coding and approval controls.\n"
                "4. Track refund + replacement leakage monthly.")
    hv = human_review.summarize()
    kind = "pending" if hv["status"] in ("missing", "pending") else hv.get("reviewer_kind")
    st.caption("Months use ticket creation date. "
               + ("Independent human validation was not completed during the assignment window." if kind == "pending" else
                  f"40-case AI secondary review by Claude: {hv['correct']}/{hv['reviewed']} exact agreement on a stratified sample. Claude also contributed to rule development, so this supplemental evidence may be optimistic and is not independent human validation." if kind == "ai" else
                  f"Independent human review: {hv['correct']}/{hv['reviewed']} agreement on a stratified sample."))

else:
    st.title("Data quality & reconciliation")
    bq = res["bridge"]
    st.subheader("Raw export → canonical, by quarter")
    st.dataframe(bq.round(0), hide_index=True)
    st.plotly_chart(px.bar(bq.melt(id_vars="quarter", value_vars=["raw_export_value", "canonical_value"]), x="quarter", y="value",
                           color="variable", barmode="group", log_y=True, title="Raw vs canonical (log scale)"))
    ev = res["scale"]
    st.write(f"**Legacy unit evidence:** {ev['pairs_exact_x100']:.0%} of {ev['pairs_with_refund']} re-imported refund pairs are exactly ×100; "
             f"median refund/retail = {ev['median_refund_to_retail_helpdesk']:.2f} (helpdesk) vs {ev['median_refund_to_retail_legacy']:.1f} (legacy).")
    st.write(f"**Duplicates:** {len(res['dropped'])} re-imported ticket_ids dropped (legacy copy). The bridge removes duplicates first, then scales the rest; "
             "scaling all legacy rows first would attribute almost the whole gap to the paise unit (totals are identical either way). **Source split:**")
    st.dataframe(res["source_split"], hide_index=True)
    st.subheader("Automated validation")
    st.dataframe(pd.DataFrame(validate.automated_checks(res, RAW_DIR)), hide_index=True)
    st.subheader("Full reconciliation table")
    st.dataframe(res["recon"], hide_index=True)

"""Public Vireo refund demo. Loads sanitized aggregate CSVs from outputs/ only."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"


@st.cache_data
def load_public_data():
    """Read the four approved public aggregate exports and nothing else."""
    reasons = pd.read_csv(OUTPUTS / "reason_code_summary.csv")
    bridge = pd.read_csv(OUTPUTS / "reconciliation_bridge_clean.csv")
    agents = pd.read_csv(OUTPUTS / "agent_totals.csv")
    sensitivity = pd.read_csv(OUTPUTS / "target_sensitivity.csv")
    return reasons, bridge, agents, sensitivity


def inr(value):
    number = int(round(abs(float(value))))
    sign = "-" if float(value) < 0 else ""
    if number < 1000:
        return f"₹{sign}{number}"
    tail = f"{number % 1000:03d}"
    number //= 1000
    groups = []
    while number:
        groups.append(f"{number % 100:02d}")
        number //= 100
    high_group = str(int(groups[-1]))
    prefix = high_group + ("," + ",".join(reversed(groups[:-1])) if len(groups) > 1 else "")
    return f"₹{sign}{prefix + ',' if prefix else ''}{tail}"


def lakh(value):
    return f"₹{value / 100_000:,.2f} lakh"


st.set_page_config(page_title="Vireo refund analysis — public demo", layout="wide")
st.title("Vireo Audio | Refund analysis")
st.caption("Public demo uses sanitized aggregate outputs only. Client raw records are not loaded.")

try:
    reasons, bridge, agents, sensitivity = load_public_data()
except (FileNotFoundError, pd.errors.EmptyDataError) as exc:
    st.error(f"A required sanitized aggregate file is missing or empty in outputs/: {type(exc).__name__}.")
    st.stop()

total = bridge.loc[bridge["quarter"].eq("TOTAL")].iloc[0]
quarters = bridge.loc[~bridge["quarter"].eq("TOTAL")].copy()
canonical = float(total["canonical_inr"])
refund_count = int(total["canonical_refund_rows"])
gw = reasons.loc[reasons["refund_reason_code"].eq("GW-OTHER")].iloc[0]


def reason_table(frame):
    display = frame.copy()
    display["refund_count"] = display["refund_count"].map(lambda value: f"{int(value):,}")
    for column in ("refund_value", "average_refund", "median_refund"):
        display[column] = display[column].map(inr)
    for column in ("pct_of_count", "pct_of_value"):
        display[column] = display[column].map(lambda value: f"{float(value):.1f}%")
    return display.rename(columns={
        "refund_reason_code": "Reason code", "refund_count": "Refunds", "refund_value": "Value (₹)",
        "average_refund": "Average refund (₹)", "median_refund": "Median refund (₹)",
        "pct_of_count": "% of count", "pct_of_value": "% of value",
    })


def sensitivity_table(frame):
    display = frame[
        ["scenario", "residual_rate", "avoided_tickets_per_quarter", "avoidable_replacement_cost_per_quarter_inr", "pct_of_quarterly_refund_value"]
    ].copy()
    display["residual_rate"] = display["residual_rate"].map(lambda value: f"{float(value):.1%}")
    display["avoided_tickets_per_quarter"] = display["avoided_tickets_per_quarter"].map(lambda value: f"{float(value):.1f}")
    display["avoidable_replacement_cost_per_quarter_inr"] = display["avoidable_replacement_cost_per_quarter_inr"].map(inr)
    display["pct_of_quarterly_refund_value"] = display["pct_of_quarterly_refund_value"].map(lambda value: f"{float(value):.1f}%")
    return display.rename(columns={
        "scenario": "Scenario", "residual_rate": "Residual rate", "avoided_tickets_per_quarter": "Avoided tickets / qtr",
        "avoidable_replacement_cost_per_quarter_inr": "Avoided cost / qtr (₹)",
        "pct_of_quarterly_refund_value": "% of quarterly refunds",
    })

page = st.sidebar.radio(
    "Page",
    [
        "1 Executive Summary",
        "2 Refund Explorer",
        "3 Agent Analysis",
        "4 Control Review",
        "5 Data Quality & Reconciliation",
        "6 Board Pack",
    ],
)

if page.startswith("1"):
    st.header("Executive Summary")
    a, b, c, d = st.columns(4)
    a.metric("Canonical refund total", inr(canonical))
    b.metric("Refund tickets", f"{refund_count:,}")
    c.metric("Average per quarter", inr(canonical / len(quarters)))
    d.metric("GW-OTHER value", lakh(float(gw["refund_value"])))
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(quarters, x="quarter", y="canonical_inr", title="Canonical refunds by quarter (₹)"),
            width="stretch",
        )
    with right:
        st.plotly_chart(
            px.bar(reasons, x="refund_reason_code", y="refund_value", title="Refund value by reason code (₹)"),
            width="stretch",
        )
    st.subheader("Reason-code summary")
    st.dataframe(reason_table(reasons), hide_index=True, width="stretch")

elif page.startswith("2"):
    st.header("Refund Explorer")
    choice = st.selectbox("Reason code", ["All"] + sorted(reasons["refund_reason_code"].dropna().unique()))
    filtered = reasons if choice == "All" else reasons.loc[reasons["refund_reason_code"].eq(choice)]
    count = int(filtered["refund_count"].sum())
    value = float(filtered["refund_value"].sum())
    average = value / count if count else 0.0
    # Median is supplied per reason; for multiple reasons a weighted median is not
    # derivable from aggregate data, so show the reason-level median only.
    median = float(filtered.iloc[0]["median_refund"]) if len(filtered) == 1 else None
    a, b, c, d = st.columns(4)
    a.metric("Refund count", f"{count:,}")
    b.metric("Refund value", inr(value))
    c.metric("Share of refund value", f"{filtered['pct_of_value'].sum():.1f}%")
    d.metric("Average refund", inr(average))
    if median is not None:
        st.metric("Median refund", inr(median))
    else:
        st.caption("Select one reason code to see its median; a portfolio median cannot be recovered from reason-level aggregates.")
    st.dataframe(
        reason_table(filtered)[["Reason code", "Refunds", "Value (₹)", "% of value", "Average refund (₹)", "Median refund (₹)"]],
        hide_index=True,
        width="stretch",
    )

elif page.startswith("3"):
    st.header("Agent Analysis")
    st.info("Agents are compared only within their own team.")
    st.warning("z_vs_team is an anomaly-review signal, not an agent performance ranking.")
    teams = sorted(agents["team"].dropna().unique())
    team = st.selectbox("Team", teams)
    selected = agents.loc[agents["team"].eq(team)].sort_values("agent_id").copy()
    st.plotly_chart(
        px.scatter(
            selected,
            x="attended",
            y="refund_rate",
            hover_name="agent_id",
            title=f"{team}: attended tickets vs refund rate",
            labels={"attended": "Tickets attended", "refund_rate": "Refund rate"},
        ),
        width="stretch",
    )
    st.dataframe(
        selected[
            [
                "agent_id", "team", "tier", "site", "attended", "refund_count", "refund_value",
                "refund_rate", "team_rate", "avg_refund", "value_per_ticket", "z_vs_team",
            ]
        ],
        hide_index=True,
        width="stretch",
    )

elif page.startswith("4"):
    st.header("Control Review")
    st.subheader("GW-OTHER requires review")
    g1, g2, g3 = st.columns(3)
    g1.metric("Refunds", f"{int(gw['refund_count']):,}")
    g2.metric("Refund value", lakh(float(gw["refund_value"])))
    g3.metric("Share of refund value", f"{float(gw['pct_of_value']):.1f}%")
    st.caption("This is a review signal, not evidence of misconduct or mis-coding. The aggregate export cannot distinguish a cap/approval issue from an ordinary refund recorded under GW-OTHER.")
    st.subheader("Replacement-cost sensitivity")
    st.info("The 1% scenario is an illustrative planning assumption, not a forecast or observed saving.")
    st.dataframe(sensitivity_table(sensitivity), hide_index=True, width="stretch")
    st.plotly_chart(
        px.bar(
            sensitivity.loc[sensitivity["basis"].eq("PLANNING ASSUMPTION")],
            x="scenario",
            y="avoidable_replacement_cost_per_quarter_inr",
            title="Illustrative avoided replacement cost by residual-rate scenario (₹/quarter)",
        ),
        width="stretch",
    )

elif page.startswith("5"):
    st.header("Data Quality & Reconciliation")
    st.caption("Bridge is computed from the sanitized aggregate reconciliation export.")
    quarter_view = quarters[
        ["quarter", "raw_export_inr", "duplicate_refund_rows_removed", "less_reimport_duplicates_inr", "less_legacy_paise_scaling_inr", "canonical_inr", "bridge_check_inr"]
    ].copy()
    for column in ("raw_export_inr", "less_reimport_duplicates_inr", "less_legacy_paise_scaling_inr", "canonical_inr", "bridge_check_inr"):
        quarter_view[column] = quarter_view[column].map(inr)
    quarter_view["duplicate_refund_rows_removed"] = quarter_view["duplicate_refund_rows_removed"].map(lambda value: f"{int(value):,}")
    quarter_view = quarter_view.rename(columns={
        "quarter": "Quarter", "raw_export_inr": "Raw export (₹)", "duplicate_refund_rows_removed": "Duplicate rows removed",
        "less_reimport_duplicates_inr": "Duplicate adjustment (₹)", "less_legacy_paise_scaling_inr": "Legacy scaling (₹)",
        "canonical_inr": "Canonical refunds (₹)", "bridge_check_inr": "Bridge (₹)",
    })
    st.dataframe(quarter_view, hide_index=True, width="stretch")
    st.metric("Total reconciliation bridge", inr(float(total["bridge_check_inr"])))
    st.success("Bridge closes to ₹0." if abs(float(total["bridge_check_inr"])) < 0.005 else "Bridge does not close; investigate before use.")
    st.plotly_chart(
        px.bar(
            quarters.melt(id_vars="quarter", value_vars=["raw_export_inr", "canonical_inr"], var_name="measure", value_name="value_inr"),
            x="quarter",
            y="value_inr",
            color="measure",
            barmode="group",
            log_y=True,
            title="Raw vs canonical quarterly value (log scale, ₹)",
        ),
        width="stretch",
    )

else:
    st.header("Board Pack | Refunds")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Raw exported total", f"₹{float(total['raw_export_inr']) / 10_000_000:,.2f} crore")
    k2.metric("Canonical total", inr(canonical))
    k3.metric("Quarterly average", inr(canonical / len(quarters)))
    latest = quarters.iloc[-1]
    k4.metric(f"Latest quarter ({latest['quarter']})", inr(float(latest["canonical_inr"])))

    st.subheader("Reconciliation")
    steps = pd.DataFrame(
        [
            ("Raw export", float(total["raw_export_inr"])),
            ("Less re-import duplicates", float(total["less_reimport_duplicates_inr"])),
            ("Less legacy paise scaling", float(total["less_legacy_paise_scaling_inr"])),
            ("Canonical total", canonical),
            ("Bridge check", float(total["bridge_check_inr"])),
        ],
        columns=["Step", "Amount (₹)"],
    )
    steps["Amount (₹)"] = steps["Amount (₹)"].map(inr)
    st.dataframe(steps, hide_index=True, width="stretch")
    st.caption(f"Reconciliation bridge: {inr(float(total['bridge_check_inr']))}")

    st.subheader("Quarterly refund position")
    st.plotly_chart(
        px.bar(quarters, x="quarter", y="canonical_inr", title="Canonical refund total by quarter (₹)"),
        width="stretch",
    )
    st.subheader("Refund drivers")
    st.dataframe(reason_table(reasons), hide_index=True, width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Control opportunity")
        st.metric("GW-OTHER", f"{int(gw['refund_count']):,} refunds")
        st.write(f"{lakh(float(gw['refund_value']))} · {float(gw['pct_of_value']):.1f}% of refund value")
        st.caption("Requires review; not evidence of misconduct or mis-coding.")
    with right:
        st.subheader("Replacement-cost scenario")
        one = sensitivity.loc[sensitivity["scenario"].str.contains("1%", regex=False)].iloc[0]
        st.metric("Illustrative 1% residual", f"{inr(float(one['avoidable_replacement_cost_per_quarter_inr']))} / quarter")
        st.caption("The 1% residual target is a planning assumption, not a forecast.")
    st.dataframe(sensitivity_table(sensitivity), hide_index=True, width="stretch")

    st.subheader("Validation and privacy")
    st.caption(
        "The analysis package contains automated validation and independent recomputation evidence. "
        "The completed analysis and dashboard were also manually reviewed by a human reviewer, as reported by the project owner. "
        "This public application uses sanitized aggregate outputs and does not load client raw CSVs or private case-level text."
    )
    st.caption("The separate 40-case AI secondary review is supplementary QA; it is not human validation.")

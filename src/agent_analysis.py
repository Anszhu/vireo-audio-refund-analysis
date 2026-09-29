import numpy as np
import pandas as pd


def monthly_agent_table(c):
    a = c.copy()
    base = a.groupby(["month", "agent_id", "agent_name", "agent_team", "agent_tier", "agent_site"]).agg(
        resolved_ticket_count=("is_attended", "sum")).reset_index()
    r = a[a["has_refund"]]
    rf = r.groupby(["month", "agent_id"]).agg(refund_count=("has_refund", "sum"),
                                              refund_value=("refund_amount_norm", "sum")).reset_index()
    ra = r[r["is_attended"]].groupby(["month", "agent_id"]).size().rename("refund_count_attended").reset_index()
    top = (r.groupby(["month", "agent_id", "refund_reason_code"]).size().rename("n").reset_index()
             .sort_values(["month", "agent_id", "n", "refund_reason_code"], ascending=[True, True, False, True])
             .drop_duplicates(["month", "agent_id"])[["month", "agent_id", "refund_reason_code"]]
             .rename(columns={"refund_reason_code": "top_reason_code"}))
    t = base.merge(rf, on=["month", "agent_id"], how="left").merge(ra, on=["month", "agent_id"], how="left") \
            .merge(top, on=["month", "agent_id"], how="left")
    for col in ["refund_count", "refund_value", "refund_count_attended"]:
        t[col] = t[col].fillna(0)
    t["refund_rate"] = t["refund_count_attended"] / t["resolved_ticket_count"].replace(0, np.nan)
    t["refund_value_per_resolved_ticket"] = t["refund_value"] / t["resolved_ticket_count"].replace(0, np.nan)
    t["average_refund"] = t["refund_value"] / t["refund_count"].replace(0, np.nan)
    t = t.rename(columns={"agent_team": "team", "agent_tier": "tier", "agent_site": "site"})
    return t


def agent_totals(c):
    """Whole-period agent metrics with a peer-group (same team) comparison - never cross-team ranking."""
    a = c.copy()
    g = a.groupby(["agent_id", "agent_name", "agent_team", "agent_tier", "agent_site"]).agg(
        attended=("is_attended", "sum"), refund_count=("has_refund", "sum"),
        refund_value=("refund_amount_norm", "sum")).reset_index()
    ra = a[a["has_refund"] & a["is_attended"]].groupby("agent_id").size().rename("refund_attended")
    g = g.merge(ra, on="agent_id", how="left").fillna({"refund_attended": 0})
    g["refund_rate"] = g["refund_attended"] / g["attended"]
    g["avg_refund"] = g["refund_value"] / g["refund_count"].replace(0, np.nan)
    g["value_per_ticket"] = g["refund_value"] / g["attended"]
    tt = g.groupby("agent_team").agg(team_att=("attended", "sum"), team_ref=("refund_attended", "sum"))
    g = g.merge(tt, on="agent_team")
    g["team_rate"] = g["team_ref"] / g["team_att"]
    # z-score of the agent's refund count vs the team rate (binomial approx.); descriptive, not a verdict
    se = np.sqrt(g["team_rate"] * (1 - g["team_rate"]) / g["attended"])
    g["z_vs_team"] = (g["refund_rate"] - g["team_rate"]) / se.replace(0, np.nan)
    g["outside_normal_range_for_team"] = g["z_vs_team"].abs() > 3
    return g.rename(columns={"agent_team": "team", "agent_tier": "tier", "agent_site": "site"})


def team_summary(c):
    g = c.groupby(["agent_team", "agent_tier"]).agg(
        attended=("is_attended", "sum"), refunds=("has_refund", "sum"),
        refund_value=("refund_amount_norm", "sum")).reset_index()
    g["refund_rate"] = g["refunds"] / g["attended"]
    g["avg_refund"] = g["refund_value"] / g["refunds"].replace(0, np.nan)
    g["share_of_refund_value"] = g["refund_value"] / g["refund_value"].sum()
    return g.sort_values("refund_value", ascending=False)


def agent_reason_mix_flags(c, min_refunds=15):
    """Agents whose GW-OTHER share differs from their team's (descriptive)."""
    r = c[c["has_refund"]]
    x = r.groupby(["agent_team", "agent_id", "agent_name"]).agg(n=("has_refund", "size"),
            gw=("refund_reason_code", lambda s: (s == "GW-OTHER").mean())).reset_index()
    x = x[x["n"] >= min_refunds]
    x["team_gw_share"] = x.groupby("agent_team")["gw"].transform("mean")
    x["gw_delta_vs_team"] = x["gw"] - x["team_gw_share"]
    return x.sort_values("gw_delta_vs_team", ascending=False)

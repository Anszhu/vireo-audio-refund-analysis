"""End-to-end run:  python -m src.pipeline   (writes data/processed + outputs; never touches data/raw)."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .ingest import load_raw
from .normalize import build_canonical
from .ai_assistant import get_classifier
from . import reconcile, refund_analysis as ra, agent_analysis as aa, exceptions as ex, target, gw_other, privacy

ROOT = Path(__file__).resolve().parents[1]
PROC, OUT = ROOT / "data" / "processed", ROOT / "outputs"
WEEKS_PER_MONTH = 4.33
TICKETS_PER_WEEK = 650
LAST_N_QUARTERS = ["2025Q4", "2026Q1", "2026Q2"]  # current run-rate window (helpdesk-native quarters)
TARGET_RATE = 0.01  # PLANNING ASSUMPTION (not a fact, not a forecast): residual 1% of refund tickets for genuine same-day-escalated errors


def business_case(c, exc):
    r = c[c["has_refund"] & c["quarter"].isin(LAST_N_QUARTERS)]
    conf = exc[(exc["exception_class"] == "confirmed") & exc["quarter"].isin(LAST_N_QUARTERS)]
    likely = exc[(exc["exception_class"] == "likely") & exc["quarter"].isin(LAST_N_QUARTERS)]
    n_q = len(LAST_N_QUARTERS)
    refund_tickets_q = len(r) / n_q
    cur_rate = len(conf) / len(r)
    cost_conf_q = conf["repl_cost_inr"].sum() / n_q
    avoidable_q = cost_conf_q * (1 - TARGET_RATE / cur_rate)
    likely_q = likely["repl_cost_inr"].sum() / n_q
    return dict(window=LAST_N_QUARTERS, refund_tickets_per_quarter=refund_tickets_q,
                confirmed_tickets=int(len(conf)), refund_tickets=int(len(r)),
                current_rate=cur_rate, target_rate=TARGET_RATE,
                confirmed_replacement_cost_per_quarter=cost_conf_q,
                avoidable_per_quarter=avoidable_q,
                likely_text_only_cost_per_quarter_not_in_goal=likely_q,
                avg_replacement_cost_confirmed=float(conf["repl_cost_inr"].mean()))


def run(raw_dir=None, write=True):
    raw = load_raw(raw_dir) if raw_dir else load_raw()
    c, dropped, parsed = build_canonical(raw)
    clf = get_classifier()
    # classify only refund rows (text QA is about refunds); keep non-refund rows unclassified
    r = clf.classify(c[c["has_refund"]])
    ai_cols = [x for x in r.columns if x.startswith("ai_")]
    c = c.merge(r[["ticket_id"] + ai_cols], on="ticket_id", how="left", validate="1:1")
    exc = ex.find_exceptions(c)
    res = dict(canonical=c, dropped=dropped, parsed=parsed, exceptions=exc,
               recon=reconcile.reconciliation_table(parsed, c, dropped),
               bridge=reconcile.bridge(parsed, c),
               scale=reconcile.scale_evidence(parsed, c, raw["products"]),
               source_split=reconcile.source_split(parsed, c),
               monthly=ra.monthly(c), quarterly=ra.quarterly(c), reasons=ra.reason_summary(c),
               agent_monthly=aa.monthly_agent_table(c), agent_totals=aa.agent_totals(c),
               team=aa.team_summary(c), gw_cap=ex.gw_over_cap(c), business=business_case(c, exc),
               raw=raw)
    res["sensitivity"] = target.sensitivity_table(
        res["business"], res["quarterly"].set_index("quarter").loc[LAST_N_QUARTERS, "refund_value"].mean())
    res["bridge_clean"] = reconcile.clean_bridge(res["bridge"])
    res["gw_metrics"] = gw_other.gw_review_metrics(c)
    res["gw_table"] = gw_other.gw_review_table(c)
    if write:
        PRIV = OUT / "private"   # git-ignored: contains customer free text and agent names (client personal data)
        PROC.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True); PRIV.mkdir(parents=True, exist_ok=True)
        id_maps = privacy.identifier_maps(c)
        c.drop(columns=["resolved_order_id"]).to_csv(PROC / "canonical_tickets.csv", index=False)
        dropped.to_csv(PROC / "dropped_reimport_rows.csv", index=False)
        # Full versions (names and notes) go to outputs/private/. Public report exports
        # use deterministic pseudonyms so joins remain inspectable without exposing IDs.
        res["agent_monthly"].to_csv(PRIV / "agent_monthly_refunds_with_names.csv", index=False)
        res["agent_totals"].to_csv(PRIV / "agent_totals_with_names.csv", index=False)
        privacy.anonymize_frame(res["agent_monthly"].drop(columns=["agent_name"]), id_maps).to_csv(OUT / "agent_monthly_refunds.csv", index=False)
        privacy.anonymize_frame(res["agent_totals"].drop(columns=["agent_name"]), id_maps).to_csv(OUT / "agent_totals.csv", index=False)
        res["reasons"].to_csv(OUT / "reason_code_summary.csv", index=False)
        privacy.anonymize_reconciliation(res["recon"], id_maps).to_csv(OUT / "refund_reconciliation.csv", index=False)
        exc.to_csv(PRIV / "refund_replacement_exceptions_with_text.csv", index=False)
        privacy.anonymize_frame(
            exc.drop(columns=["customer_message", "agent_notes", "agent_name"]), id_maps
        ).to_csv(OUT / "refund_replacement_exceptions.csv", index=False)
        res["sensitivity"].to_csv(OUT / "target_sensitivity.csv", index=False)
        res["bridge_clean"].to_csv(OUT / "reconciliation_bridge_clean.csv", index=False)
        res["gw_table"].to_csv(OUT / "gw_other_review.csv", index=False)
        (PROC / "business_case.json").write_text(json.dumps(res["business"], indent=2, default=float))
    return res


if __name__ == "__main__":
    res = run()
    print(json.dumps(res["business"], indent=2, default=float))

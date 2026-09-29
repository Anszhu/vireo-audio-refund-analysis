"""Sensitivity of the avoidable replacement cost to the residual refund+replacement rate.

FACT (from data, last-3-quarter window): current confirmed rate and the replacement cost of confirmed cases
(policy s5: unit cost + Rs 340, no refurbishment recovery).
PLANNING ASSUMPTION: the residual rate that remains after a control fix. It is not observed, not proven and
not a forecast - the table simply shows what each assumed residual would be worth.

Method (same as pipeline.business_case): avoidable cost per quarter =
    confirmed replacement cost per quarter x (1 - residual_rate / current_rate)
i.e. cases are assumed to fall proportionally, at the average replacement cost of the confirmed cases.
"""
import pandas as pd

RESIDUAL_RATES = [0.05, 0.03, 0.02, 0.01, 0.00]
DISCLAIMER = "The 1% target is a planning assumption, not a forecast."


def sensitivity_table(business, refund_value_per_quarter, rates=RESIDUAL_RATES):
    b = business
    cur = b["current_rate"]
    n_q = len(b["window"])
    rows = [dict(scenario="Current (observed)", basis="FACT", residual_rate=cur,
                 confirmed_tickets_per_quarter=b["confirmed_tickets"] / n_q, avoided_tickets_per_quarter=0.0,
                 avoidable_replacement_cost_per_quarter_inr=0.0)]
    for rr in rates:
        resid = min(rr, cur)  # a residual above today's rate would mean no improvement
        rows.append(dict(scenario=f"Residual {rr:.0%}" + (" (illustrative target)" if abs(rr - 0.01) < 1e-9 else ""),
                         basis="PLANNING ASSUMPTION", residual_rate=rr,
                         confirmed_tickets_per_quarter=b["refund_tickets_per_quarter"] * resid,
                         avoided_tickets_per_quarter=b["refund_tickets_per_quarter"] * (cur - resid),
                         avoidable_replacement_cost_per_quarter_inr=b["confirmed_replacement_cost_per_quarter"] * (1 - resid / cur)))
    t = pd.DataFrame(rows)
    t["pct_of_quarterly_refund_value"] = 100 * t["avoidable_replacement_cost_per_quarter_inr"] / refund_value_per_quarter
    t["window"] = "+".join(b["window"])
    t["note"] = DISCLAIMER
    return t

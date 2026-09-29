"""Refund + replacement exception detection (policy s5: never both for the same order).

Classification (documented, deliberately conservative):
  confirmed  - SAME ticket has a refund amount AND replacement_issued = Y (two system-of-record
               fields agree) and the agent note does not say the replacement was declined/rejected.
  likely     - (a) same ticket has a refund and the NOTE says both remedies were given but the
                   replacement flag is N (text-only evidence), or
  ambiguous  - refund + flag Y but the note says the replacement was declined/rejected
               (fields contradict text); note only mentions a replacement/reship without a clear
               both-remedies statement; or a DIFFERENT ticket for the same exact order_id carries
               replacement_issued=Y (may be a separate incident, so NOT counted as a violation).
Evidence sources: classification uses the structured fields (refund amount, replacement_issued), the agent note and
cross-ticket/order evidence only; the customer message is shown as supporting context, never used to classify.
Replacement cost = unit_cost_inr + Rs 340 (policy s5). Refurbishment recovery NOT assumed.
"""
import numpy as np
import pandas as pd
from .ai_assistant import REPL_MENTION, _norm

REPL_EXTRA_COST = 340
COLS = ["ticket_id", "created_at", "month", "quarter", "customer_id", "resolved_order_id", "order_id",
        "order_join", "refund_amount_norm", "refund_reason_code", "replacement_issued", "product_sku",
        "product_name", "agent_id", "agent_name", "agent_team", "assigned_team", "source_system",
        "customer_message", "agent_notes"]


def find_exceptions(c):
    c = c.copy()
    c["repl_cost_inr"] = c["unit_cost_inr"] + REPL_EXTRA_COST
    r = c[c["has_refund"]].copy()
    sig = r["ai_replacement_signal"]
    both_fields = r["replacement_issued"].eq("Y")
    r["exception_class"] = np.select(
        [both_fields & ~sig.eq("declined_or_not_given"),
         both_fields & sig.eq("declined_or_not_given"),
         ~both_fields & sig.eq("both_remedies_stated"),
         ~both_fields & sig.eq("replacement_mentioned")],
        ["confirmed", "ambiguous", "likely", "ambiguous"], default="")
    cls = r["exception_class"]
    declined = both_fields & sig.eq("declined_or_not_given")
    # (mask, evidence text, evidence source, classification label) - first match wins
    rules = [
        (cls.eq("confirmed"), "refund amount and replacement_issued=Y on same ticket",
         np.where(sig.isin(["both_remedies_stated", "replacement_mentioned"]),
                  "structured field + agent note", "structured field"),
         "Refund + replacement recorded on same ticket"),
        (declined, "replacement_issued=Y but note says replacement declined/rejected",
         "structured field vs agent note (contradiction)", "Replacement flag Y but note says declined"),
        (cls.eq("likely"), "note states both remedies given; replacement_issued=N (text-only)",
         "agent note", "Note states refund and replacement both given"),
        (cls.eq("ambiguous"), "note mentions replacement/reship; flag N (unclear whether one was sent)",
         "agent note", "Note mentions a replacement; unclear if sent"),
    ]
    r["evidence"], r["evidence_source"], r["classification"] = "", "", ""
    for mask, ev, src, lab in rules:
        hit_r = mask & (r["evidence"] == "")
        r.loc[hit_r, "evidence"] = ev
        r.loc[hit_r, "evidence_source"] = (src[hit_r.to_numpy()] if isinstance(src, np.ndarray) else src)
        r.loc[hit_r, "classification"] = lab
    # cross-ticket: same order_id (quoted or inferred - see evidence_source), refund on one ticket and replacement Y on another
    repl = c[(c["replacement_issued"] == "Y") & c["order_id"].notna()][["ticket_id", "order_id"]]
    x = r[r["order_id"].notna() & r["exception_class"].eq("")].merge(
        repl, on="order_id", suffixes=("", "_repl"))
    x = x[x["ticket_id"] != x["ticket_id_repl"]]
    hit = r["ticket_id"].isin(x["ticket_id"])
    r.loc[hit, "exception_class"] = "ambiguous"
    r.loc[hit, "evidence"] = "same order_id: refund here, replacement_issued=Y on another ticket (may be separate incident)"
    inferred = r["order_join"].eq("fallback_cust_sku")
    r.loc[hit & ~inferred, "evidence_source"] = "cross-ticket/order evidence (order_id quoted on ticket)"
    r.loc[hit & inferred, "evidence_source"] = "cross-ticket/order evidence (order inferred from customer+SKU)"
    r.loc[hit, "classification"] = "Refund here; replacement on another ticket of same order"
    ex = r[r["exception_class"] != ""].copy()
    ex["cross_ticket_partner"] = ex["ticket_id"].map(x.groupby("ticket_id")["ticket_id_repl"].first())
    ex["text_corroborated"] = ex["ai_replacement_signal"].isin(["both_remedies_stated", "replacement_mentioned"])
    ex["order_id_basis"] = ex["order_join"].map({"order_id": "quoted on ticket", "fallback_cust_sku": "inferred (customer+SKU)"}).fillna("none")
    ex["confidence"] = ex["exception_class"].str.capitalize()   # Confirmed / Likely / Ambiguous
    # supporting context only - NOT used to classify: does the customer's own message mention a replacement?
    ex["customer_message_mentions_replacement"] = [bool(REPL_MENTION.search(_norm(m))) for m in ex["customer_message"]]
    out = ex[COLS + ["exception_class", "confidence", "classification", "evidence", "evidence_source",
                     "customer_message_mentions_replacement", "order_id_basis", "text_corroborated", "cross_ticket_partner", "repl_cost_inr"]]
    order = {"confirmed": 0, "likely": 1, "ambiguous": 2}
    return out.sort_values(["exception_class", "created_at"], key=lambda s: s.map(order) if s.name == "exception_class" else s)\
              .reset_index(drop=True)


def gw_over_cap(c, cap=500):
    r = c[c["has_refund"] & (c["refund_reason_code"] == "GW-OTHER")]
    return r[r["refund_amount_norm"] > cap]

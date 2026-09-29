"""Build the canonical ticket-level analytical dataset.

Every transformation is deliberate and documented in DATA_AUDIT.md:
  1. Dates parsed (helpdesk display timestamps are IST; created_at is used for month/quarter
     because resolved_at on legacy rows was rebuilt from a UTC event log - policy s9).
  2. Duplicates: a ticket_id that appears under BOTH source systems is a migration re-import.
     We keep ONE row (the helpdesk copy, already in rupees) and drop the legacy copy.
  3. Legacy money: legacy_fd stores paise (x100). Divisor is derived from data, not assumed
     (see reconcile.scale_evidence) and applied only to legacy rows that are kept.
  4. Joins: order by order_id; fallback customer_id + product_sku (latest order on/before ticket).
  5. Agent roster joined by agent_id + assignment date window, never by name.
"""
import numpy as np
import pandas as pd

GO_LIVE = pd.Timestamp("2025-09-14")
LEGACY_DIVISOR = 100  # evidence: reconcile.scale_evidence()
REASON_CODES = ["GW-OTHER", "DOA-REPL", "LOST-TRANSIT", "DUP-PAYMENT", "CANCEL",
                "PRICE-ADJ", "RETURN-QC-OK", "WTY-BUYBACK"]


def parse_tickets(t):
    t = t.copy()
    for c in ["created_at", "first_response_at", "resolved_at"]:
        t[c] = pd.to_datetime(t[c], format="%Y-%m-%d %H:%M", errors="coerce")
    t["refund_amount_raw"] = pd.to_numeric(t["refund_amount_inr"], errors="coerce")
    t["transfers"] = pd.to_numeric(t["transfers"], errors="coerce")
    t["csat_score"] = pd.to_numeric(t["csat_score"], errors="coerce")
    return t


def dedupe(t):
    """Return (canonical rows, audit table of dropped rows)."""
    src_per_id = t.groupby("ticket_id")["source_system"].nunique()
    reimport_ids = set(src_per_id[src_per_id > 1].index)
    t = t.copy()
    t["in_reimport_pair"] = t["ticket_id"].isin(reimport_ids)
    t["_pri"] = np.where(t["source_system"] == "helpdesk", 0, 1)
    t = t.sort_values(["ticket_id", "_pri"], kind="stable")
    dropped = t[t.duplicated("ticket_id", keep="first")].drop(columns="_pri")
    kept = t.drop_duplicates("ticket_id", keep="first").drop(columns="_pri")
    return kept.reset_index(drop=True), dropped.reset_index(drop=True)


def apply_money_normalisation(t):
    t = t.copy()
    legacy = t["source_system"] == "legacy_fd"
    t["scale_divisor"] = np.where(legacy, LEGACY_DIVISOR, 1)
    t["refund_amount_norm"] = t["refund_amount_raw"] / t["scale_divisor"]
    t["has_refund"] = t["refund_amount_norm"].notna()
    return t


def join_orders(t, orders, products, customers):
    t = t.copy()
    o = orders.rename(columns={"customer_id": "o_customer_id", "sku": "o_sku", "channel": "order_channel"})
    o["order_date"] = pd.to_datetime(o["order_date"])
    t = t.merge(o, on="order_id", how="left", validate="m:1")
    t["order_join"] = np.where(t["order_id"].isna(), "no_order_id",
                        np.where(t["order_date"].notna(), "order_id", "order_id_not_found"))
    # integrity of the order_id join
    t["order_cust_mismatch"] = (t["order_join"] == "order_id") & (t["o_customer_id"] != t["customer_id"])
    t["order_sku_mismatch"] = (t["order_join"] == "order_id") & (t["o_sku"] != t["product_sku"])
    # fallback: customer_id + sku, latest order on/before ticket creation
    need = t["order_id"].isna()
    fb = o.rename(columns={"o_customer_id": "customer_id", "o_sku": "product_sku"})
    cand = t.loc[need, ["ticket_id", "customer_id", "product_sku", "created_at"]].merge(
        fb, on=["customer_id", "product_sku"], how="inner")
    cand = cand[cand["order_date"] <= cand["created_at"].dt.normalize()]
    cand = cand.sort_values(["ticket_id", "order_date"]).drop_duplicates("ticket_id", keep="last")
    cols = ["order_id", "order_date", "order_channel", "qty", "order_value_inr", "lot_code"]
    fbm = cand.set_index("ticket_id")[cols]
    hit = t["ticket_id"].isin(fbm.index) & need
    for c in cols:
        t.loc[hit, c] = t.loc[hit, "ticket_id"].map(fbm[c])
    t["resolved_order_id"] = t["order_id"]  # after fallback
    t.loc[hit, "order_join"] = "fallback_cust_sku"
    t.loc[need & ~hit, "order_join"] = "unmatched"
    t = t.merge(products.rename(columns={"sku": "product_sku"}), on="product_sku", how="left", validate="m:1")
    t = t.merge(customers[["customer_id", "care_plus", "signup_date"]], on="customer_id", how="left", validate="m:1")
    return t


def join_agents(t, agents):
    """Assignment-window join on agent_id."""
    a = agents.copy()
    a["from_date"] = pd.to_datetime(a["from_date"])
    a["to_date"] = pd.to_datetime(a["to_date"])
    a = a.rename(columns={"name": "agent_name", "team": "agent_team", "site": "agent_site",
                          "shift": "agent_shift", "tier": "agent_tier"})
    a["agent_tier"] = a["agent_tier"].astype(int)
    m = t[["ticket_id", "agent_id", "created_at"]].merge(a, on="agent_id", how="left")
    d = m["created_at"].dt.normalize()
    m["in_window"] = (d >= m["from_date"]) & (m["to_date"].isna() | (d <= m["to_date"]))
    m = m.sort_values(["ticket_id", "in_window", "from_date"]).drop_duplicates("ticket_id", keep="last")
    m["roster_match"] = np.where(m["agent_name"].isna(), "agent_not_in_roster",
                                 np.where(m["in_window"], "in_window", "outside_window"))
    keep = ["ticket_id", "agent_name", "agent_team", "agent_tier", "agent_site", "agent_shift", "roster_match"]
    return t.merge(m[keep], on="ticket_id", how="left", validate="1:1")


def build_canonical(raw):
    t = parse_tickets(raw["tickets"])
    kept, dropped = dedupe(t)
    kept = apply_money_normalisation(kept)
    kept = join_orders(kept, raw["orders"], raw["products"], raw["customers"])
    kept = join_agents(kept, raw["agents"])
    kept["month"] = kept["created_at"].dt.to_period("M").astype(str)
    kept["quarter"] = kept["created_at"].dt.to_period("Q").astype(str)
    kept["is_attended"] = kept["status"].isin(["resolved", "closed"])  # policy s10
    return kept, dropped, t

import pandas as pd


def refunds(c):
    return c[c["has_refund"]].copy()


def monthly(c):
    r = refunds(c)
    return r.groupby("month")["refund_amount_norm"].agg(refund_count="count", refund_value="sum",
                                                          average_refund="mean").reset_index()


def quarterly(c):
    r = refunds(c)
    return r.groupby("quarter")["refund_amount_norm"].agg(refund_count="count", refund_value="sum",
                                                            average_refund="mean").reset_index()


def reason_summary(c):
    r = refunds(c)
    g = r.groupby("refund_reason_code")["refund_amount_norm"].agg(
        refund_count="count", refund_value="sum", average_refund="mean", median_refund="median").reset_index()
    g["pct_of_count"] = 100 * g["refund_count"] / g["refund_count"].sum()
    g["pct_of_value"] = 100 * g["refund_value"] / g["refund_value"].sum()
    return g.sort_values("refund_value", ascending=False).reset_index(drop=True)


def reason_monthly(c):
    r = refunds(c)
    return r.pivot_table(index="month", columns="refund_reason_code", values="refund_amount_norm",
                         aggfunc=["count", "sum"], fill_value=0)


def reason_by_quarter(c):
    r = refunds(c)
    return r.pivot_table(index="quarter", columns="refund_reason_code", values="refund_amount_norm",
                         aggfunc="sum", fill_value=0)


def context_table(c, by):
    """Refund incidence per attended ticket, by any dimension (family, channel, care_plus, sku, ...)."""
    a = c[c["is_attended"]]
    g = a.groupby(by).agg(tickets=("ticket_id", "size"), refunds=("has_refund", "sum"),
                          refund_value=("refund_amount_norm", "sum")).reset_index()
    g["refund_rate"] = g["refunds"] / g["tickets"]
    g["avg_refund"] = g["refund_value"] / g["refunds"].replace(0, float("nan"))
    return g.sort_values("refund_value", ascending=False)

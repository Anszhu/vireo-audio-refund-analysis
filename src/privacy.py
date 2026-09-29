"""Deterministic pseudonyms for identifier-bearing public report exports.

The analytical pipeline keeps source identifiers internally so joins and
validation remain intact. Files written under outputs/ use stable labels and
never include a reversible mapping table.
"""
import hashlib
import pandas as pd


def _mapping(values, prefix):
    clean = {str(value) for value in values if pd.notna(value) and str(value).strip()}
    # The fixed per-ID digest keeps labels stable across files and future runs,
    # without numbering IDs in source order or publishing a mapping table.
    result = {}
    for value in clean:
        digest = hashlib.sha256((prefix.lower() + "|" + value).encode("utf-8")).hexdigest()[:10].upper()
        result[value] = f"{prefix}-{digest}"
    return result


def identifier_maps(canonical):
    """Build cross-file stable maps from the full canonical population."""
    order_values = pd.concat(
        [canonical.get("order_id", pd.Series(dtype="object")),
         canonical.get("resolved_order_id", pd.Series(dtype="object"))],
        ignore_index=True,
    )
    ticket_map = _mapping(canonical.get("ticket_id", []), "case")
    return {
        "ticket_id": ticket_map,
        "customer_id": _mapping(canonical.get("customer_id", []), "customer"),
        "order_id": _mapping(order_values, "order"),
        "resolved_order_id": _mapping(order_values, "order"),
        "agent_id": _mapping(canonical.get("agent_id", []), "agent"),
        "product_sku": _mapping(canonical.get("product_sku", []), "sku"),
        "cross_ticket_partner": ticket_map,
    }


def anonymize_frame(frame, maps):
    """Return a copy with known identifier columns replaced consistently."""
    safe = frame.copy()
    for column, mapping in maps.items():
        if column in safe.columns:
            safe[column] = safe[column].map(
                lambda value: mapping.get(str(value), value) if pd.notna(value) else value
            )
    return safe


def anonymize_reconciliation(frame, maps):
    """Pseudonymize the agent key held in reconciliation row labels."""
    safe = frame.copy()
    mask = safe["section"].eq("G_agent_canonical")
    safe.loc[mask, "item"] = safe.loc[mask, "item"].map(
        lambda value: maps["agent_id"].get(str(value), value)
    )
    return safe


"""Text QA layer over customer_message / agent_notes.

Design
------
* Deterministic, rule-based (regex + keyword) -> reproducible, no API key, no paid model.
* The dropdown `refund_reason_code` stays the source of record. This layer only produces
  QA *flags* and a *suggested* reason so a human reviewer can prioritise.
* No LLM/API is called anywhere. `get_classifier()` is the single seam where an LLM-backed
  classifier could be swapped in later. Cost of the submitted run: Rs 0.
"""
import re
import numpy as np
import pandas as pd

# --- topic rules (searched in agent_notes first, then customer_message) -----------------
TOPIC_RULES = [
    ("dup_payment", r"duplicate (payment|txn|charge)|double charge|charged (two|twice)|two entries|payment debited|amount deducted|deducted without|failed payment|utr|\bpg\b.*(txn|dashboard)|card charged"),
    ("cancel", r"cancel|don'?t ship|ordered (by mistake|the wrong)"),
    ("price_adj", r"coupon|discount|promo|price (drop|match|adj)|cart (says|eligib)|20% off|invoice shows"),
    ("return_qc", r"reverse (pickup|pkp|pkup) (pending|not|missed)|qc status|refund (not|nt) (received|rcvd)|refund (was )?promised|money (hasn'?t|has not) come|amount is nowhere|return was accepted|rf(u)?nd delay|rfd status|refund delay|(pickup|pkp) (missed|awb|not done|pending|missed|reschedul)|return(ed)? (received|qc)|rfnd not credited|refund not credited|refund pending|refund status|rfnd status|re-?raised pickup|nobody came for|pickup today|no one showed"),
    ("damaged_wrong", r"damaged|transit damage|dent|crack|crushed|wrong (variant|item|product|colou?r)|different colou?r|incorrect product|different (thing|product)|doa\b|dead on arrival|got something else|kicked|not the item"),
    ("lost_transit", r"not (delivered|received|rcvd)|shipment not|undelivered|\brto\b|\bawb\b|courier|dlvry delayed|ord not delivered|nothing in hand|haven'?t received my order|missing parcel|lost in transit"),
    ("warranty", r"warranty|\brma\b|repair|esc(alated)? to wty"),
    ("goodwill", r"goodwill|one-time gesture|as a gesture|courtesy"),
]
TOPIC_RULES = [(k, re.compile(p, re.I)) for k, p in TOPIC_RULES]

# recorded codes acceptable for each inferred topic (policy s5)
ACCEPTABLE = {
    "dup_payment": {"DUP-PAYMENT"},
    "cancel": {"CANCEL"},
    "price_adj": {"PRICE-ADJ"},
    "lost_transit": {"LOST-TRANSIT"},
    "damaged_wrong": {"DOA-REPL", "LOST-TRANSIT"},   # damaged-in-transit has no own code
    "return_qc": {"RETURN-QC-OK"},
    "warranty": {"WTY-BUYBACK", "DOA-REPL"},
    "goodwill": {"GW-OTHER"},
}

LOW_INFO = re.compile(r"^\W*(cx ok|done|see prev|-|ok|noted|closed|resolved|\(sop [\d.]+\))?\W*(\(sop [\d.]+\))?\W*$", re.I)

# --- refund + replacement signals ---------------------------------------------------------
NO_REPL = re.compile(r"(replacement|rplc) (request )?(was )?(rejected|declined|not applicable)|"
                     r"cx preferred (refund|rfnd)|cx opted for (refund|rfnd)|explained policy, refund only|"
                     r"(replacement|rplc) was offered earlier|offered (replacement|rplc)|refund only|"
                     r"(replacement|rplc) not applicable|declined by cx|refund issued instead|(refund|rfnd) only", re.I)
BOTH_REPL = re.compile(r"also sending a new|fresh (pair|unit) shipped|new set|new piece dispatched|fr (&|and) raised rma|\bboth\b|refund (\+|&|and) (replacement|rplc)|rfnd (\+|&|and) (replacement|rplc)|"
                       r"(refund|rfnd|refunded).{0,20}(and )?also (raised|shipped|sent|dispatched).{0,15}(replacement|rplc)?|"
                       r"new unit also|new unit (sent|going out)|(replacement|rplc) unit also|"
                       r"released the money as well|(replacement|rplc) dispatched as goodwill|"
                       r"dispatched a new one|one-time gesture", re.I)
REPL_MENTION = re.compile(r"replacement|rplc|new unit|new one|reship|re-ship", re.I)


def _norm(s):
    return re.sub(r"\s+", " ", str(s if s == s and s is not None else "")).strip().lower()


def infer_topic(notes, message):
    """Return (topic, source) using notes first, then customer message."""
    n, m = _norm(notes), _norm(message)
    for src, txt in (("notes", n), ("message", m)):
        for topic, rx in TOPIC_RULES:
            if rx.search(txt):
                return topic, src
    return "unknown", "none"


def replacement_signal(notes):
    n = _norm(notes)
    if NO_REPL.search(n):
        return "declined_or_not_given"
    if BOTH_REPL.search(n):
        return "both_remedies_stated"
    if REPL_MENTION.search(n):
        return "replacement_mentioned"
    return "none"


class RuleBasedClassifier:
    name = "rules-v1"
    cost_per_ticket_inr = 0.0

    def classify(self, df):
        out = df.copy()
        tp = [infer_topic(n, m) for n, m in zip(out["agent_notes"], out["customer_message"])]
        out["ai_topic"] = [a for a, _ in tp]
        out["ai_topic_source"] = [b for _, b in tp]
        out["ai_replacement_signal"] = [replacement_signal(n) for n in out["agent_notes"]]
        out["ai_low_info_note"] = [bool(LOW_INFO.match(_norm(n))) for n in out["agent_notes"]]
        acc = out["ai_topic"].map(ACCEPTABLE)
        out["ai_suggested_codes"] = acc.apply(lambda s: "|".join(sorted(s)) if isinstance(s, set) else "")
        rec = out["refund_reason_code"]
        ok = [(isinstance(a, set) and r in a) for a, r in zip(acc, rec)]
        known = out["ai_topic"] != "unknown"
        out["ai_code_matches_text"] = np.where(known, ok, np.nan)
        out["ai_gw_specific_reason"] = (rec == "GW-OTHER") & known & (out["ai_topic"] != "goodwill")
        out["ai_code_mismatch"] = known & (rec != "GW-OTHER") & ~pd.Series(ok, index=out.index)
        out["ai_needs_review"] = out["ai_gw_specific_reason"] | out["ai_code_mismatch"] | \
            out["ai_replacement_signal"].eq("both_remedies_stated")
        return out


def get_classifier():
    return RuleBasedClassifier()

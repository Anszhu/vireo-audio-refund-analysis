import sys
from pathlib import Path
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import pipeline, validate, ai_assistant
from src.ingest import RAW_DIR

HAS_DATA = (Path(RAW_DIR) / "tickets.csv").exists()


@pytest.fixture(scope="module")
def res():
    if not HAS_DATA:
        pytest.skip("data-dependent test: private assignment dataset not present in data/raw/ (see data/README.md)")
    return pipeline.run(write=False)


def test_automated_checks_all_pass(res):
    checks = validate.automated_checks(res, RAW_DIR)
    failed = [c for c in checks if not c["passed"]]
    assert not failed, failed


def test_legacy_scaling_is_evidence_based(res):
    ev = res["scale"]
    assert ev["pairs_exact_x100"] == 1.0 and ev["pairs_with_refund"] > 50


def test_bridge_closes(res):
    b = res["bridge"]
    assert abs((b.raw_export_value + b.less_reimport_duplicates_value + b.less_legacy_unit_scaling_value - b.canonical_value).sum()) < 0.01


def test_raw_files_untouched():
    import hashlib
    m = Path(RAW_DIR).parent / "raw_checksums.txt"
    if not HAS_DATA:
        pytest.skip("data-dependent test: private assignment dataset not present in data/raw/ (see data/README.md)")
    if not m.exists():
        pytest.skip("no checksum manifest")
    checked = 0
    for line in m.read_text().splitlines():
        h, f = line.split()
        if (Path(RAW_DIR) / f).exists():           # the policy PDF is optional
            assert hashlib.sha256((Path(RAW_DIR) / f).read_bytes()).hexdigest() == h, f
            checked += 1
    assert checked >= 5


@pytest.mark.parametrize("notes,expected", [
    ("issued refund + replacement both, tl aware", "both_remedies_stated"),
    ("cx asked for replacement + rfnd, explained policy, rfnd only.", "declined_or_not_given"),
    ("offered replacement, cx preferred refund", "declined_or_not_given"),
    ("Refund processed to source; replacement unit also shipped.", "both_remedies_stated"),
    ("cancelled before dispatch -> refunded rs 617", "none"),
])
def test_replacement_signal_rules(notes, expected):
    assert ai_assistant.replacement_signal(notes) == expected


@pytest.mark.parametrize("notes,msg,topic", [
    ("chk pg for duplicate txn", "", "dup_payment"),
    ("cancelled before dispatch", "", "cancel"),
    ("pkp missed. re-raised pkp with courier", "", "return_qc"),
    ("done", "coupon code not working", "price_adj"),
    ("cx ok", "", "unknown"),
])
def test_topic_rules(notes, msg, topic):
    assert ai_assistant.infer_topic(notes, msg)[0] == topic


def test_exception_classes_conservative(res):
    ex = res["exceptions"]
    assert set(ex.exception_class) <= {"confirmed", "likely", "ambiguous"}
    amb = ex[ex.exception_class == "ambiguous"]
    assert len(amb) > 0
    conf = ex[ex.exception_class == "confirmed"]
    assert (conf.replacement_issued == "Y").all()


def test_agent_not_joined_by_name(res):
    c = res["canonical"]
    assert c["agent_id"].notna().all() and c["agent_name"].notna().all()


def test_manual_sample_metrics_computable():
    m = validate.manual_metrics()
    assert m["holdout"]["n"] == 40 and m["dev"]["n"] == 60


# ---- audit-pass tests -------------------------------------------------------------------------------
import re
from src import human_review, target, gw_other


def test_tickets_per_month_is_644_not_resolved_only(res):
    c = res["canonical"]
    assert len(c) == 11600 and c["month"].nunique() == 18
    assert round(c.groupby("month").size().mean()) == 644


def test_sensitivity_matches_business_case_and_is_monotone(res):
    s = res["sensitivity"]; b = res["business"]
    one = s[s.scenario.str.startswith("Residual 1%")].iloc[0]
    assert abs(one.avoidable_replacement_cost_per_quarter_inr - b["avoidable_per_quarter"]) < 0.01
    plan = s[s.basis == "PLANNING ASSUMPTION"].sort_values("residual_rate", ascending=False)
    assert plan.avoidable_replacement_cost_per_quarter_inr.is_monotonic_increasing
    zero = plan[plan.residual_rate == 0].iloc[0]
    assert abs(zero.avoidable_replacement_cost_per_quarter_inr - b["confirmed_replacement_cost_per_quarter"]) < 0.01
    assert (s.note == target.DISCLAIMER).all()


def test_gw_review_metrics_consistent(res):
    g = res["gw_metrics"]; c = res["canonical"]
    r = c[c.has_refund]
    assert g["gw_refunds"] == int((r.refund_reason_code == "GW-OTHER").sum())
    assert g["gw_over_cap"] == len(res["gw_cap"]) <= g["gw_refunds"]
    assert g["over_cap_text_names_other_reason"] + g["over_cap_text_says_goodwill"] + g["over_cap_text_uninformative"] == g["gw_over_cap"]


def test_exception_evidence_columns_complete(res):
    ex = res["exceptions"]
    for col in ["ticket_id", "customer_id", "order_id", "refund_amount_norm", "refund_reason_code", "replacement_issued",
                "agent_id", "created_at", "classification", "confidence", "evidence", "evidence_source"]:
        assert col in ex.columns
        if col != "order_id":                      # order_id may legitimately be blank (no order quoted)
            assert ex[col].notna().all(), col
    assert (ex.evidence != "").all() and (ex.evidence_source != "").all()
    assert set(ex.confidence) <= {"Confirmed", "Likely", "Ambiguous"}
    assert ex[ex.evidence_source.str.startswith("cross-ticket")].exception_class.eq("ambiguous").all()   # never upgraded


def test_human_review_sheet_is_unfilled_or_valid(res):
    p = human_review.REVIEW_CSV
    if not p.exists():
        pytest.skip("review sheet not generated")
    d = human_review.load(p)
    assert len(d) == 40 and d.ticket_id.is_unique
    assert not (set(d.ticket_id) & human_review._previously_used_ids())
    s = human_review.summarize(p)
    if s["status"] == "pending":                       # nothing fabricated: every label column empty
        assert (d[["human_label", "human_confidence", "reviewer_type", "correct"]] == "").all().all()
        return
    # a filled sheet: valid labels, every row typed, `correct` consistent with the labels, not a copy of the prediction
    assert set(d.human_label.str.lower()) <= set(human_review.LABELS)
    assert set(d.reviewer_type.str.lower()) <= set(human_review.REVIEWER_TYPES)
    assert set(d.human_confidence.str.lower()) <= {"high", "medium", "low"}
    same = d.existing_prediction.str.lower() == d.human_label.str.lower()
    assert (d.correct.str.lower().map({"yes": True, "no": False}) == same).all()
    assert not same.all(), "labels identical to predictions on all rows - looks copied"
    for col in ["evidence_basis", "evidence_source", "reasoning", "policy_reference"]:
        assert (d[col].str.strip() != "").all(), col
    # the sheet must never carry customer free text or names
    assert not {"customer_message", "agent_notes", "customer_name", "agent_name"} & set(d.columns)
    if s["reviewer_kind"] == "ai":                      # an AI review must never be presented as independent human validation
        assert not s["independent_complete"]


def test_human_review_scoring_logic(tmp_path):
    import pandas as pd
    d = pd.DataFrame({"ticket_id": list("abcd"), "existing_prediction": ["confirmed", "likely", "not_confirmed", "ambiguous"],
                      "human_label": ["confirmed", "not_confirmed", "likely", ""], "human_confidence": ["high"] * 4,
                      "evidence_basis": ["both"] * 4, "correct": [""] * 4, "review_notes": [""] * 4, "reviewer_type": ["independent"] * 4})
    f = tmp_path / "h.csv"; d.to_csv(f, index=False)
    s = human_review.score_in_place(f)
    assert (s["reviewed"], s["correct"], s["incorrect"], s["fp"], s["fn"]) == (3, 1, 2, 1, 1)
    assert s["status"] == "partial"
    empty = d.assign(human_label=""); empty.to_csv(f, index=False)
    assert human_review.summarize(f)["status"] == "pending"


def test_no_llm_or_network_dependency_in_src():
    banned = re.compile(r"^\s*(import|from)\s+(anthropic|openai|requests|urllib\.request|httpx|google\.generativeai)\b", re.M)
    for f in (Path(__file__).resolve().parents[1] / "src").glob("*.py"):
        assert not banned.search(f.read_text(encoding="utf-8")), f


def test_public_outputs_have_no_customer_text_or_agent_names(res):
    out = Path(__file__).resolve().parents[1] / "outputs"
    for name in ["refund_replacement_exceptions.csv", "agent_totals.csv", "agent_monthly_refunds.csv", "refund_reconciliation.csv"]:
        cols = pd.read_csv(out / name, nrows=1).columns
        assert not {"customer_message", "agent_notes", "agent_name", "name"} & set(cols), name
    for f in (Path(__file__).resolve().parents[1] / "validation").glob("*.csv"):
        if f.name != "human_review.csv":
            assert not {"customer_message", "agent_notes"} & set(pd.read_csv(f, nrows=1).columns), f


def test_bridge_clean_closes_and_matches_canonical(res):
    b = res["bridge_clean"]
    assert (b["bridge_check_inr"].abs() < 0.01).all()
    tot = b[b.quarter == "TOTAL"].iloc[0]
    assert abs(tot.canonical_inr - res["canonical"]["refund_amount_norm"].sum()) < 0.01
    assert abs(tot.raw_export_inr - res["parsed"]["refund_amount_raw"].sum()) < 0.01


def test_gw_definitions_are_separate(res):
    g = res["gw_metrics"]
    assert g["gw_value"] > g["gw_over_cap_value"] > 0          # total GW-OTHER value vs above-cap subset value are different metrics
    assert abs(g["gw_over_cap_pct_of_gw"] - 100 * g["gw_over_cap"] / g["gw_refunds"]) < 1e-9


def test_public_review_summary_has_only_aggregates(res):
    f = Path(__file__).resolve().parents[1] / "validation" / "review_summary.csv"
    if not human_review.REVIEW_CSV.exists() or human_review.summarize()["status"] in ("missing", "pending"):
        pytest.skip("no completed review")
    d = pd.read_csv(f)
    assert list(d.columns) == ["sample_size", "correct_count", "incorrect_count", "ambiguous_count", "accuracy", "error_rate",
                               "false_positive_count", "false_negative_count", "confirmed_count", "likely_count",
                               "ambiguous_distribution", "not_confirmed_count", "reviewer_type"]
    assert len(d) == 1 and d.sample_size.iloc[0] == 40
    assert d.correct_count.iloc[0] + d.incorrect_count.iloc[0] == 40
    assert d.confirmed_count.iloc[0] + d.likely_count.iloc[0] + d.ambiguous_count.iloc[0] + d.not_confirmed_count.iloc[0] == 40
    assert not d.astype(str).apply(lambda col: col.str.contains("TK-")).any().any()      # no ticket ids

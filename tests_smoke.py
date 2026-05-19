from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from run_compliance_check import resolve_input_path, resolve_product_definitions
from src.engine import analyze_trades, load_trades, run_pipeline


def run_report(regimes: list[str]) -> dict:
    with TemporaryDirectory(prefix="hw2_smoke_") as tmp:
        tmp_root = Path(tmp)
        return run_pipeline(
            resolve_input_path(Path("data/processed/trades.json")),
            resolve_product_definitions(Path("data/product_definitions")),
            regimes,
            tmp_root / "output",
            tmp_root / "dashboard",
        )


def test_key_homework_cases() -> None:
    report = run_report(["CFTC", "MAS"])
    by_id = {row["trade_id"]: row for row in report["trades"]}
    assert report["metadata"]["trade_count"] == 28
    assert by_id["T005"]["overall_status"] == "WARNING"
    assert any(item["rule_id"] == "LIBOR_WARNING" for item in by_id["T005"]["findings"])
    assert by_id["T008"]["upi"]["codeset_results"]["notional_currency"]["status"] == "VALID"
    assert by_id["T013"]["parse"]["engine_parse_status"] == "PARTIAL"
    assert any(item["rule_id"] == "MAS_NULL_MARGIN" for item in by_id["T017"]["findings"])
    assert by_id["T026"]["upi"]["upi_status"] == "NO_PRODUCT_DEFINITION"
    assert by_id["T027"]["overall_status"] == "NOT_REPORTABLE"
    assert by_id["T027"]["data_quality_status"] == "NONCOMPLIANT"
    assert by_id["T027"]["reporting_scope_status"] == "OUT_OF_SCOPE"
    assert by_id["T027"]["regulatory_conclusion"] == "NOT_REPORTABLE_EVENT_CONTRACT"
    assert by_id["T027"]["economic_function_test"]["engine_conclusion"] == "NOT_REPORTABLE_EVENT_CONTRACT"
    assert by_id["T027"]["supervisory_flags"]["recommended_cftc_action"] == "EC1_REVIEW_BELOW_PROPOSED_THRESHOLD"
    assert by_id["T028"]["classification_conclusion"] == "CONDITIONAL_EVENT_CONTRACT"
    assert "schema_proposal" in report["event_contract_analysis"]
    assert "MAS_SG_NEXUS" not in report["summary"]["top_compliance_rule_counts"]


def test_emir_homework_regime() -> None:
    report = run_report(["CFTC", "EMIR"])
    by_id = {row["trade_id"]: row for row in report["trades"]}
    mas_report = run_report(["CFTC", "MAS"])
    mas_by_id = {row["trade_id"]: row for row in mas_report["trades"]}
    assert report["metadata"]["trade_count"] == 28
    assert by_id["T013"]["parse"]["engine_parse_status"] == "PARTIAL"
    assert all(by_id[trade_id]["upi"]["upi_status"] == "NO_PRODUCT_DEFINITION" for trade_id in ["T026", "T027", "T028"])
    assert any(item["rule_id"] == "EMIR_NULL_MARGIN" for item in by_id["T017"]["findings"])
    assert any(item["rule_id"] == "MAS_NULL_MARGIN" for item in mas_by_id["T017"]["findings"])
    assert by_id["T026"]["supervisory_flags"]["recommended_cftc_action"] == "PART45_DCM_EVENT_REPORTING_CANDIDATE"
    assert not any(item["rule_id"] == "REGIME_UNSUPPORTED" and item["regime"] == "EMIR" for row in report["trades"] for item in row["findings"])


def test_additional_report_test_cases() -> None:
    product_definitions = resolve_product_definitions(Path("data/product_definitions"))
    base_trades = load_trades(resolve_input_path(Path("data/processed/trades.json")))
    base_by_id = {row["trade_id"]: row for row in base_trades}

    at004 = deepcopy(base_by_id["T002"])
    at004["trade_id"] = "AT004"
    at004["uti"] = "5493001KJTIIGC8Y1R1220250103TRDAT004"
    at004["other_counterparty_lei"] = "XKZZ2JZF41MRHTR1V494"

    at005 = deepcopy(base_by_id["T014"])
    at005["trade_id"] = "AT005"
    at005["asset_class"] = "Credit"
    at005["instrument_type"] = "CreditDefaultSwap"
    at005["use_case"] = "Index"
    at005["uti"] = "5493001KJTIIGC8Y1R1220251001TRDAT005"
    at005["booked_in_sg"] = True
    at005["traded_in_sg"] = True
    at005["initial_margin_posted"] = None
    at005["variation_margin_posted"] = None
    at005["collateral_margin_posted"] = None

    report = analyze_trades([at004, at005], product_definitions, ["CFTC", "MAS"])
    by_id = {row["trade_id"]: row for row in report["trades"]}
    assert any(item["rule_id"] == "LEI_CHECK_DIGIT" for item in by_id["AT004"]["findings"])
    assert any(item["rule_id"] == "MAS_NULL_MARGIN" for item in by_id["AT005"]["findings"])


def test_no_external_project_fallback() -> None:
    external_fallback_name = "HW2" + "_test1"
    for path in [
        Path("run_compliance_check.py"),
        Path("tools/prepare_data.py"),
        Path("tools/data_audit.py"),
        Path("src/engine.py"),
    ]:
        assert external_fallback_name not in path.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_key_homework_cases()
    test_emir_homework_regime()
    test_additional_report_test_cases()
    test_no_external_project_fallback()
    print("Smoke tests passed")

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_TRADES = ROOT / "data" / "processed" / "trades.json"
RAW_TRADES = ROOT / "data" / "raw" / "trades.json"
PRODUCT_DEFINITIONS = ROOT / "data" / "product_definitions"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def product_definitions_root() -> Path:
    return PRODUCT_DEFINITIONS


def trades_path() -> Path:
    if PROCESSED_TRADES.exists():
        return PROCESSED_TRADES
    return RAW_TRADES


def codeset(name: str) -> set[str]:
    path = product_definitions_root() / "PROD" / "OTC-Products" / "codesets" / f"{name}.json"
    if not path.exists():
        return set()
    return set(load_json(path).get("enum", []))


def main() -> None:
    trades = load_json(trades_path())
    currencies = codeset("ISOCurrencyCode")
    rates = set()
    for name in [
        "FpmlRatesReferenceRate",
        "FpmlRatesReferenceAndInflationRate",
        "ISORatesReferenceRate",
        "ISORatesReferenceAndInflationRate",
    ]:
        rates.update(codeset(name))

    by_asset = Counter(t.get("asset_class", "UNKNOWN") for t in trades)
    parse_declared = Counter(t.get("declared_parse_status", t.get("parse_status", "UNSPECIFIED")) for t in trades)
    null_margin = [
        t["trade_id"]
        for t in trades
        if any(t.get(field) is None for field in ["initial_margin_posted", "variation_margin_posted", "collateral_margin_posted"])
    ]
    event_trades = [t["trade_id"] for t in trades if t.get("asset_class") == "EventContract"]
    invalid_currencies = [
        (t["trade_id"], t.get("notional_currency"))
        for t in trades
        if t.get("notional_currency") not in currencies
    ]
    libor_rates = [
        (t["trade_id"], t.get("reference_rate"))
        for t in trades
        if isinstance(t.get("reference_rate"), str) and "LIBOR" in t["reference_rate"]
    ]
    missing_lei = [
        t["trade_id"]
        for t in trades
        if t.get("reporting_counterparty_lei") in (None, "", "MISSING_LEI")
        or t.get("other_counterparty_lei") in (None, "", "MISSING_LEI")
    ]
    non_utc_timestamps = [
        (t["trade_id"], t.get("timestamp"))
        for t in trades
        if not (isinstance(t.get("timestamp"), str) and t["timestamp"].endswith("Z") and "T" in t["timestamp"])
    ]
    unknown_rates = [
        (t["trade_id"], t.get("reference_rate"))
        for t in trades
        if t.get("reference_rate") is not None and t.get("reference_rate") not in rates
    ]

    report = {
        "trade_count": len(trades),
        "trade_source": display_path(trades_path()),
        "product_definitions_source": display_path(product_definitions_root()),
        "asset_class_counts": dict(by_asset),
        "declared_parse_status_counts": dict(parse_declared),
        "event_trades": event_trades,
        "null_margin_trades": null_margin,
        "missing_lei_trades": missing_lei,
        "invalid_currency_candidates": invalid_currencies,
        "non_utc_timestamp_candidates": non_utc_timestamps,
        "libor_reference_rates": libor_rates,
        "reference_rates_not_exactly_in_codesets": unknown_rates,
        "codeset_checks": {
            "XAU_in_currency_codeset": "XAU" in currencies,
            "USDC_in_currency_codeset": "USDC" in currencies,
            "CNH_in_currency_codeset": "CNH" in currencies,
            "GBP_LIBOR_BBA_in_rates_codeset": "GBP-LIBOR-BBA" in rates,
        },
    }
    out = ROOT / "output" / "data_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

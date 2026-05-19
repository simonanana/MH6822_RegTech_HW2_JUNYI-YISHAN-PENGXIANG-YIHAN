from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.engine import run_pipeline


BASE_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the HW2 OTC derivatives trade reporting compliance engine."
    )
    parser.add_argument("--input", default="data/processed/trades.json", help="Path to processed trades.json")
    parser.add_argument(
        "--regimes",
        default="CFTC,EMIR",
        help="Comma-separated reporting regimes. Default: CFTC,EMIR. This implementation supports CFTC, MAS, and homework-level EMIR.",
    )
    parser.add_argument(
        "--product-definitions",
        default="data/product_definitions",
        help="Path to ANNA-DSB Product-Definitions repository.",
    )
    parser.add_argument("--output-dir", default="output", help="Directory for JSON/CSV outputs")
    parser.add_argument("--dashboard-dir", default="dashboard", help="Directory for dashboard HTML")
    return parser.parse_args()


def project_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return BASE_DIR / path


def product_definitions_ready(path: Path) -> bool:
    return (
        path.exists()
        and (path / "PROD" / "OTC-Products" / "UPI").exists()
        and (path / "PROD" / "OTC-Products" / "codesets").exists()
    )


def resolve_input_path(path: Path) -> Path:
    candidates = [
        path,
        project_path(path),
        BASE_DIR / "data" / "processed" / "trades.json",
        BASE_DIR / "data" / "raw" / "trades.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Trade input file not found. Run python tools/prepare_data.py "
        "or pass --input /path/to/trades.json."
    )


def resolve_product_definitions(path: Path) -> Path:
    candidates = [
        path,
        project_path(path),
        BASE_DIR / "data" / "product_definitions",
    ]
    for candidate in candidates:
        if product_definitions_ready(candidate):
            return candidate
    raise FileNotFoundError(
        "ANNA-DSB Product-Definitions not found. Run python tools/prepare_data.py "
        "or pass --product-definitions /path/to/product_definitions."
    )


def main() -> int:
    args = parse_args()
    input_path = resolve_input_path(Path(args.input))
    output_dir = project_path(Path(args.output_dir))
    dashboard_dir = project_path(Path(args.dashboard_dir))
    regimes = [item.strip().upper() for item in args.regimes.split(",") if item.strip()]
    product_definitions = resolve_product_definitions(Path(args.product_definitions))

    report = run_pipeline(input_path, product_definitions, regimes, output_dir, dashboard_dir)
    summary = report["summary"]
    print("Compliance engine completed")
    print(f"Trades processed: {report['metadata']['trade_count']}")
    print(f"Regimes: {', '.join(report['metadata']['regimes'])}")
    print(f"Overall status counts: {summary['overall_status_counts']}")
    top_counts = summary.get("top_substantive_rule_counts", summary["top_rule_counts"])
    print(f"Top substantive rule counts: {dict(list(top_counts.items())[:8])}")
    print(f"Wrote: {output_dir / 'compliance_report.json'}")
    print(f"Wrote: {output_dir / 'findings.csv'}")
    print(f"Wrote: {dashboard_dir / 'dashboard.html'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

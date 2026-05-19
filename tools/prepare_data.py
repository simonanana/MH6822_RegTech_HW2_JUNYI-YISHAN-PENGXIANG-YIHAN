from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ROOT_TRADES = ROOT / "trades.json"
LEGACY_DATA_TRADES = DATA_DIR / "trades.json"
RAW_TRADES = RAW_DIR / "trades.json"
PROCESSED_TRADES = PROCESSED_DIR / "trades.json"
PRODUCT_DEFINITIONS = DATA_DIR / "product_definitions"
ANNA_DSB_REPO = "https://github.com/ANNA-DSB/Product-Definitions.git"

LOCAL_PRODUCT_DEFINITION_CANDIDATES: list[Path] = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare local data files for the HW2 compliance engine."
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "link"],
        default="copy",
        help="How to populate data/product_definitions from an existing local source.",
    )
    parser.add_argument(
        "--product-source",
        help="Existing local ANNA-DSB Product-Definitions path to copy or link.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Clone ANNA-DSB Product-Definitions if no local source is found.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing prepared data files.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_trade(raw: dict[str, Any]) -> dict[str, Any]:
    trade = dict(raw)
    if "parse_status" in trade and "declared_parse_status" not in trade:
        trade["declared_parse_status"] = trade.pop("parse_status")
    for old_name, new_name in [
        ("cftc_status", "case_file_cftc_status"),
        ("emir_status", "case_file_emir_status"),
        ("finding", "case_file_regulatory_note"),
    ]:
        if old_name in trade and new_name not in trade:
            trade[new_name] = trade.pop(old_name)
    return trade


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def is_product_definitions_root(path: Path) -> bool:
    return (
        path.exists()
        and (path / "PROD" / "OTC-Products" / "UPI").exists()
        and (path / "PROD" / "OTC-Products" / "codesets").exists()
    )


def find_product_source(explicit: str | None) -> Path | None:
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(LOCAL_PRODUCT_DEFINITION_CANDIDATES)
    for candidate in candidates:
        if is_product_definitions_root(candidate):
            return candidate
    return None


def ensure_trades(force: bool) -> int:
    source_candidates = [RAW_TRADES, LEGACY_DATA_TRADES, ROOT_TRADES]
    source = next((path for path in source_candidates if path.exists()), None)
    if source is None:
        raise FileNotFoundError("Missing assignment trades file. Expected data/raw/trades.json or a legacy trades.json.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    if (force or not RAW_TRADES.exists()) and source.resolve() != RAW_TRADES.resolve():
        shutil.copy2(source, RAW_TRADES)

    trades = load_json(RAW_TRADES)
    if not isinstance(trades, list):
        raise ValueError(f"{RAW_TRADES} must contain a JSON list.")
    processed = [normalize_trade(trade) for trade in trades]
    if force or not PROCESSED_TRADES.exists() or load_json(PROCESSED_TRADES) != processed:
        write_json(PROCESSED_TRADES, processed)
    return len(trades)


def remove_existing_target() -> None:
    if PRODUCT_DEFINITIONS.is_symlink() or PRODUCT_DEFINITIONS.is_file():
        PRODUCT_DEFINITIONS.unlink()
    elif PRODUCT_DEFINITIONS.exists():
        shutil.rmtree(PRODUCT_DEFINITIONS)


def populate_product_definitions(args: argparse.Namespace) -> tuple[str, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if PRODUCT_DEFINITIONS.exists():
        if is_product_definitions_root(PRODUCT_DEFINITIONS) and (not args.force or (not args.product_source and not args.download)):
            return "existing", str(PRODUCT_DEFINITIONS)
        if not args.force:
            raise FileExistsError(
                f"{PRODUCT_DEFINITIONS} exists but does not look like ANNA-DSB Product-Definitions. "
                "Rerun with --force after checking the directory."
            )
        remove_existing_target()

    source = find_product_source(args.product_source)
    if source:
        if args.mode == "link":
            PRODUCT_DEFINITIONS.symlink_to(source.resolve(), target_is_directory=True)
            return "linked", str(source)
        shutil.copytree(
            source,
            PRODUCT_DEFINITIONS,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )
        return "copied", str(source)

    if args.download:
        subprocess.run(
            ["git", "clone", "--depth", "1", ANNA_DSB_REPO, str(PRODUCT_DEFINITIONS)],
            check=True,
        )
        return "downloaded", ANNA_DSB_REPO

    raise FileNotFoundError(
        "Could not find ANNA-DSB Product-Definitions locally. "
        "Pass --product-source /path/to/Product-Definitions or rerun with --download."
    )


def write_manifest(trade_count: int, product_action: str, product_source: str) -> Path:
    product_readme = PRODUCT_DEFINITIONS / "README.md"
    clean_product_source = product_source
    try:
        source_path = Path(product_source)
        if source_path.resolve() == PRODUCT_DEFINITIONS.resolve():
            clean_product_source = str(PRODUCT_DEFINITIONS.relative_to(ROOT))
        elif source_path.is_absolute():
            try:
                clean_product_source = str(source_path.resolve().relative_to(ROOT))
            except ValueError:
                clean_product_source = "external local Product-Definitions source"
    except (OSError, ValueError):
        pass
    manifest = {
        "raw_trade_file": str(RAW_TRADES.relative_to(ROOT)),
        "raw_trade_sha256": sha256(RAW_TRADES),
        "processed_trade_file": str(PROCESSED_TRADES.relative_to(ROOT)),
        "processed_trade_sha256": sha256(PROCESSED_TRADES),
        "trade_count": trade_count,
        "product_definitions_path": str(PRODUCT_DEFINITIONS.relative_to(ROOT)),
        "product_definitions_action": product_action,
        "product_definitions_source": clean_product_source,
        "product_definitions_version": sha256(product_readme)[:16] if product_readme.exists() else "unknown",
        "normalization": [
            "parse_status -> declared_parse_status",
            "cftc_status/emir_status/finding -> case_file_* source-fact fields",
        ],
        "generated_outputs": [
            "output/compliance_report.json",
            "output/findings.csv",
            "output/summary.json",
            "output/data_audit.json",
            "dashboard/dashboard.html",
        ],
    }
    path = DATA_DIR / "data_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    trade_count = ensure_trades(args.force)
    product_action, product_source = populate_product_definitions(args)
    manifest = write_manifest(trade_count, product_action, product_source)

    print("Data preparation completed")
    print(f"Raw trades: {RAW_TRADES.relative_to(ROOT)} ({trade_count} records)")
    print(f"Processed trades: {PROCESSED_TRADES.relative_to(ROOT)}")
    print(f"Product definitions: {PRODUCT_DEFINITIONS.relative_to(ROOT)} ({product_action})")
    print(f"Source: {product_source}")
    print(f"Manifest: {manifest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

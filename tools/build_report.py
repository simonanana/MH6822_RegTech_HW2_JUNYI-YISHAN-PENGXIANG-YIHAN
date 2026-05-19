from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        "| " + " | ".join(cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell(item) for item in row) + " |")
    return "\n".join(out)


def dict_rows(mapping: dict[str, int]) -> list[list[object]]:
    return [[k, v] for k, v in mapping.items()]


def counted_rule_list(rule_ids: list[str]) -> str:
    counts: dict[str, int] = {}
    for rule_id in rule_ids:
        counts[rule_id] = counts.get(rule_id, 0) + 1
    return ", ".join(
        f"{rule_id} x{count}" if count > 1 else rule_id
        for rule_id, count in counts.items()
    ) or "none"


DISPLAY_LABELS = {
    "WARNING": "Warning",
    "NONCOMPLIANT": "Non-compliant",
    "PASS": "Pass",
    "IN_SCOPE": "In scope",
    "OUT_OF_SCOPE": "Out of scope",
    "CONDITIONAL": "Conditional",
    "AMBIGUOUS": "Ambiguous",
    "CONVENTIONAL": "Conventional",
    "CONDITIONAL_EVENT_CONTRACT": "Conditional event contract",
    "NOT_REPORTABLE_EVENT_CONTRACT": "Not-reportable event contract",
    "REGULATORY_AMBIGUOUS": "Regulatory ambiguous",
    "NOT_REPORTABLE": "Not reportable",
}


TEAM_ROSTER = {
    "LIU YISHAN": "G2505246J",
    "GONG PENG XIANG": "G2505431H",
    "GUO YIHAN": "G2506255B",
    "ZHANG JUNYI": "G2505266E",
}


def display_label(value: object) -> str:
    return DISPLAY_LABELS.get(str(value), str(value).replace("_", " ").title())


def compact_status(value: object) -> str:
    labels = {
        "YES_FUNCTIONAL_NOT_LEGAL": "YES (functional, not legal)",
        "CONDITIONAL_EVENT_CONTRACT": "Conditional",
        "NOT_REPORTABLE_EVENT_CONTRACT": "Not reportable",
    }
    return labels.get(str(value), str(value).replace("_", " ").title())


def roster_id(name: str) -> str:
    """Return the canonical student ID for a named team member."""
    return TEAM_ROSTER[name]


def display_rows(mapping: dict[str, int]) -> list[list[object]]:
    return [[display_label(k), v] for k, v in mapping.items()]


PRODUCT_LABELS = {
    ("Rates", "Swap", "Fixed_Float"): "Rates swap",
    ("Rates", "Swap", "OIS"): "Rates OIS",
    ("FX", "Swap", "FX_Swap"): "FX swap",
    ("Commodities", "Swap", "CommoditySwap"): "Commodity swap",
}


def display_product(raw: dict[str, object], product: dict[str, str] | None) -> str:
    key = (str(raw.get("asset_class")), str(raw.get("instrument_type")), str(raw.get("use_case")))
    if key in PRODUCT_LABELS:
        return PRODUCT_LABELS[key]
    if product:
        return f"{product['asset_class'].replace('Foreign_Exchange', 'FX')} {product['instrument_type']}"
    return "No OTC template"


def short_hash(value: str | None) -> str:
    return value[:12] if value else "not recorded"


def main() -> None:
    audit = load_json(ROOT / "output" / "data_audit.json")
    report = load_json(ROOT / "output" / "compliance_report.json")
    manifest = load_json(ROOT / "data" / "data_manifest.json")
    raw_trades = {row["trade_id"]: row for row in load_json(ROOT / "data" / "processed" / "trades.json")}
    summary = report["summary"]
    trades = {row["trade_id"]: row for row in report["trades"]}
    event_analysis = report.get("event_contract_analysis", {})

    parse_rows = dict_rows(summary["parse_status_counts"])
    overall_rows = display_rows(summary["overall_status_counts"])
    data_quality_rows = display_rows(summary["data_quality_status_counts"])
    scope_rows = display_rows(summary["reporting_scope_status_counts"])
    conclusion_rows = display_rows(summary["regulatory_conclusion_counts"])
    rule_rows = dict_rows(
        summary.get(
            "top_substantive_rule_counts",
            summary.get("top_compliance_rule_counts", summary["top_rule_counts"]),
        )
    )[:12]
    scope_rule_rows = dict_rows(summary.get("scope_rule_counts", {}))[:8]
    asset_rows = dict_rows(audit["asset_class_counts"])

    attribute_rows = []
    attribute_items = []
    for tid in ["T001", "T005", "T015", "T024", "T026"]:
        row = trades[tid]
        raw = raw_trades[tid]
        validation = row["upi"].get("required_attribute_validation", {})
        product = row["upi"].get("normalized_product")
        product_label = display_product(raw, product)
        status_label = {
            "NO_PRODUCT_DEFINITION": "NO TEMPLATE",
            "NO_TEMPLATE_MATCH": "NO MATCH",
        }.get(validation.get("status", "UNKNOWN"), validation.get("status", "UNKNOWN"))
        attribute_rows.append(
            [
                tid,
                product_label,
                status_label,
                validation.get("checked_required_count", 0),
                validation.get("missing_mapped_required_count", 0),
                validation.get("unmapped_required_count", 0),
            ]
        )
        attribute_items.append(
            f"- **{tid}**: {product_label}; required status {status_label}; "
            f"checked {validation.get('checked_required_count', 0)}, "
            f"missing mapped {validation.get('missing_mapped_required_count', 0)}, "
            f"unmapped {validation.get('unmapped_required_count', 0)}."
        )

    event_rows = [
        [
            "T026",
            f"{raw_trades['T026']['platform']} / CFTC DCM",
            "Election subsidy hedge",
            "EU gambling/public-policy issue; no OTC UPI",
            "Ambiguous",
        ],
        [
            "T027",
            f"{raw_trades['T027']['platform']} / offshore",
            "CPI/USD bond exposure hedge",
            "No LEI, USDC settlement, no CFTC DCM",
            "Not reportable",
        ],
        [
            "T028",
            f"{raw_trades['T028']['platform']} / CFTC DCM",
            "AI Act compliance-cost hedge",
            "Regulatory decision event; no OTC UPI",
            "Ambiguous",
        ],
    ]
    economic_function_rows = []
    economic_function_details = []
    for tid in ["T026", "T027", "T028"]:
        test = trades[tid].get("economic_function_test") or event_analysis.get("economic_function_tests", {}).get(tid, {})
        if not test:
            continue
        economic_function_rows.append(
            [
                tid,
                compact_status(test["quantifiable_exposure"]["status"]),
                compact_status(test["viable_hedge_substitute"]["status"]),
                compact_status(test["price_discovery_beyond_public_data"]["status"]),
                compact_status(test["engine_conclusion"]),
            ]
        )
        economic_function_details.append(
            f"- **{tid} ({raw_trades[tid]['platform']}/{raw_trades[tid]['use_case']}) rationale**: "
            f"Q1 {test['quantifiable_exposure']['rationale']} "
            f"Q2 {test['viable_hedge_substitute']['rationale']} "
            f"Q3 {test['price_discovery_beyond_public_data']['rationale']}"
        )
    schema_json = json.dumps(event_analysis.get("schema_proposal", {}), indent=2)
    schema_summary_rows = [
        [
            "EventCategory",
            "Classifies political, macro, regulatory, weather, litigation, or other events.",
        ],
        [
            "ReferenceEntity",
            "Identifies the official body, index, court, regulator, or source resolving the event.",
        ],
        [
            "EventJurisdiction / EventDate",
            "Records where and when the event is determined.",
        ],
        [
            "ResolutionSource",
            "Defines the authoritative source used for settlement.",
        ],
        [
            "PayoutType",
            "Captures binary, scalar, capped, floored, or multi-outcome payoff.",
        ],
        [
            "SettlementCurrency",
            "Captures fiat or stablecoin settlement and flags non-ISO identifiers.",
        ],
        [
            "PlatformType",
            "Distinguishes CFTC DCM, offshore exchange, decentralised protocol, bilateral OTC, or other venues.",
        ],
        [
            "RegulatoryStatus",
            "Records approved, conditional, prohibited, not applicable, or uncertain status.",
        ],
    ]
    cftc_recommendation_items = []
    for item in event_analysis.get("cftc_recommendations", []):
        cftc_recommendation_items.append(
            f"- **{item['recommendation_id']}**: {item['title']} {item['engine_impact']}"
        )
    supervisory_flag_rows = []
    for tid in ["T026", "T027", "T028"]:
        flags = trades[tid].get("supervisory_flags") or {}
        if flags:
            supervisory_flag_rows.append(
                [
                    tid,
                    flags["no_upi_taxonomy"],
                    flags["non_iso_settlement_currency"],
                    flags["missing_identifier_visibility"],
                    flags["ec1_threshold_status"],
                    flags["recommended_cftc_action"],
                ]
            )

    contribution_rows = [
        [
            roster_id("LIU YISHAN"),
            "LIU YISHAN",
            "Data pipeline and trade parser",
            "Raw/processed data review; parser handling; nulls, bad dates, partial timestamps.",
            "M1 / Integration",
        ],
        [
            roster_id("GONG PENG XIANG"),
            "GONG PENG XIANG",
            "UPI lookup and ANNA-DSB taxonomy validation",
            "ANNA-DSB template lookup; product alias mapping; currency/reference-rate codesets; EventContract no-product-definition.",
            "M2 / UPI Lookup Engine",
        ],
        [
            roster_id("GUO YIHAN"),
            "GUO YIHAN",
            "Compliance checker and regime validation",
            "LEI/UTI checks; CFTC/EMIR field validation; null-versus-zero margin logic; tests.",
            "M3 / Testing",
        ],
        [
            roster_id("ZHANG JUNYI"),
            "ZHANG JUNYI",
            "Classification analysis, report, and dashboard integration",
            "Prediction-market analysis; economic function test; EventContract schema; regulatory arbitrage; report/dashboard integration.",
            "M4 / Dashboard / Final Report",
        ],
    ]
    additional_test_rows = [
        ["AT001", "Credit CDS/SingleName clean control", "No hard compliance failure expected"],
        ["AT002", "FX VanillaOption clean control", "No hard compliance failure expected"],
        ["AT003", "Equity option with Singapore booking/trading nexus", "MAS_SG_NEXUS scope note"],
        ["AT004", "Rates IRS with wrong LEI check digit", "LEI check-digit failure"],
        ["AT005", "Credit index with three null margin fields", "EMIR or MAS null-margin failure"],
    ]

    trade_finding_rows = [
        [
            "T005",
            "Warning / In scope",
            "`LIBOR_WARNING`",
            "Legacy benchmark warning, not a hard failure.",
        ],
        [
            "T008",
            "Non-compliant / In scope",
            "`LEI_CHECK_DIGIT`",
            "Invalid LEI check digit.",
        ],
        [
            "T013",
            "Warning / In scope",
            "`TIMESTAMP_PARTIAL`",
            "Date-only timestamp; identifiable but not fully ISO UTC.",
        ],
        [
            "T017",
            "Non-compliant / In scope",
            "`EMIR_REQUIRED_FIELD`; `EMIR_NULL_MARGIN` x3",
            "Null margin is not zero under EMIR.",
        ],
        [
            "T021",
            "Non-compliant / In scope",
            "`LEI_MISSING`; `UTI_NAMESPACE`; `UTI_NAMESPACE_FORMAT`; `CFTC_REQUIRED_FIELD`; `EMIR_REQUIRED_FIELD`",
            "Identifier and required-field failure.",
        ],
        [
            "T023",
            "Non-compliant / In scope",
            "`UTI_NAMESPACE`; `UTI_NAMESPACE_FORMAT`; `UTI_SUFFIX`",
            "UTI namespace/suffix defect.",
        ],
        [
            "T025",
            "Non-compliant / In scope",
            "`TIMESTAMP_INVALID`",
            "Unparseable timestamp.",
        ],
        [
            "T026",
            "Warning / Conditional",
            "`NO_PRODUCT_DEFINITION`",
            "EventContract outside ANNA-DSB OTC taxonomy.",
        ],
        [
            "T027",
            "Non-compliant / Out of scope",
            "`NO_PRODUCT_DEFINITION`; `INVALID_CURRENCY`; `LEI_MISSING` x2; `UTI_MISSING`",
            "Data-quality failure but not visible through the CFTC/EMIR OTC reporting path.",
        ],
        [
            "T028",
            "Warning / Conditional",
            "`NO_PRODUCT_DEFINITION`",
            "EventContract outside ANNA-DSB OTC taxonomy.",
        ],
    ]

    content = f"""# OTC Derivatives Trade Reporting Compliance Engine and Prediction Market Classification Frontier

*A rule-based RegTech pipeline for UPI, UTI, LEI, CFTC/EMIR validation and EventContract classification analysis.*

## 1. Thesis and Data Lineage

The engine finds that conventional OTC products can be mapped and checked through existing UPI, UTI, and LEI infrastructure, but prediction market contracts expose a taxonomy and visibility gap: they may transfer real economic risk without producing standard trade-reporting identifiers. This report is therefore not only a JSON validation exercise. It is a data-driven regulatory analysis of where current reporting infrastructure works, where it flags bad data, and where it runs out of product-classification vocabulary.

The rebuilt data chain is auditable:

{md_table(["Layer", "File", "SHA-256 / version"], [
    ["Raw source facts", manifest["raw_trade_file"], short_hash(manifest.get("raw_trade_sha256"))],
    ["Processed normalized trades", manifest["processed_trade_file"], short_hash(manifest.get("processed_trade_sha256"))],
    ["Product definitions", "data/product_definitions", manifest.get("product_definitions_version", "not recorded")],
])}

`data/raw/trades.json` is treated as the immutable case-file input. `data/processed/trades.json` is the normalized runtime file. The normalizer renames the raw `parse_status` to `declared_parse_status` and moves event-contract conclusion-like fields into `case_file_*` source facts. The engine then produces its own parse result, compliance findings, scope assessments, and regulatory conclusions. This avoids blindly trusting labels in the raw data while preserving the original case-file facts for audit.

The portfolio contains {audit["trade_count"]} trade records across six asset-class labels:

{md_table(["Asset class", "Trades"], asset_rows)}

The data audit found:

- Event contracts: {", ".join(audit["event_trades"])}
- Null margin records: {", ".join(audit["null_margin_trades"])}
- Missing or placeholder LEI records: {", ".join(audit["missing_lei_trades"])}
- Non-UTC or invalid timestamps: {", ".join(f"{tid} ({value})" for tid, value in audit["non_utc_timestamp_candidates"])}
- Invalid or non-ISO currency candidates: {", ".join(f"{tid} ({value})" for tid, value in audit["invalid_currency_candidates"])}
- Legacy LIBOR reference-rate candidate: {", ".join(f"{tid} ({value})" for tid, value in audit["libor_reference_rates"])}

The codeset checks are important. `XAU` is present in the DSB ISO currency codeset and must not be failed. `GBP-LIBOR-BBA` is present in the rates codeset, but it is a legacy LIBOR benchmark and should be a warning rather than a hard failure. `USDC` and `CNH` are not in the DSB ISO currency codeset used by this homework data.

## 2. Regulatory Framing

The assignment is about post-crisis OTC derivatives transparency. The engine is therefore organized around the three identifier pillars: UPI for product identity, UTI for transaction identity, and LEI for party identity. CFTC is treated as the baseline reporting regime, while EMIR is used as the primary second-regime validation run, consistent with the assignment reference command. MAS is retained as an alternative Singapore-focused run because the portfolio includes Singapore booking/trading fields.

The stronger framing is:

> A rule-based RegTech engine for OTC derivatives trade reporting, with a classification analysis showing how prediction market contracts expose the boundary of current derivatives reporting taxonomy.

This framing matches the homework modules: parse all 28 trades, match ANNA-DSB product definitions, check CFTC/EMIR rules, and then analyze whether event contracts should be brought into reporting infrastructure.

## 3. Engine Architecture

The pipeline is:

```bash
python run_compliance_check.py --input data/processed/trades.json --regimes CFTC,EMIR
```

The implementation uses only the Python standard library. LEI check digits are validated directly using ISO 7064 MOD 97-10 logic. UPI lookup reads DSB JSON schema files from:

```text
PROD/OTC-Products/UPI/{{AssetClass}}/{{AssetClass}}.{{InstrumentType}}.{{UseCase}}.UPI.V1.json
```

The architecture separates ingestion, normalization, validation, regime-specific checks, event-contract classification, and reporting outputs. Raw fields are preserved for auditability, while parse status, UPI status, compliance findings, scope assessments, and classification conclusions are generated by the pipeline. Product-label aliases are stored in `config/product_aliases.json`, and regime requirements are exposed through a `REGIME_RULES` mapping so additional jurisdictions can be added without rewriting the core analysis loop. `src/engine.py` is kept as the stable shared implementation layer, while the Module 1-4 wrapper files expose the homework architecture without duplicating logic.

The parser result is:

{md_table(["Engine parse status", "Count"], parse_rows)}

The parser deliberately distinguishes declared source labels from engine results. T013 has a date-only timestamp, so the record is identifiable but not fully ISO 8601 UTC compliant. T022 has an invalid maturity date (`99999-12-31`), so it is also partial even though the raw case file declared it as `OK`. T025 is failed because its timestamp is `NOT_A_DATE`.

The validation stack now includes business-consistency checks in addition to field presence: date order, timestamp versus trade date, positive notional amount, non-negative margin, boolean `cleared`, and allowed `action_type` values. This is closer to production trade-reporting validation than a simple null check.

## 4. UPI Lookup and Codeset Validation

The UPI module performs template lookup against ANNA-DSB. Some teaching-data product labels are not identical to production taxonomy labels, so the engine normalizes them through a transparent alias layer and records the mapping as a normalization note rather than a substantive compliance failure. For example, `VanillaOption` maps to `Vanilla_Option`, `OIS` maps to `Fixed_Float_OIS`, and `CommoditySwap` maps to the DSB commodity swap template.

Important Module 2 findings:

- T008 passes currency validation because `XAU` is a valid code in `ISOCurrencyCode.json`.
- T005 receives `LIBOR_WARNING` because `GBP-LIBOR-BBA` remains in the codeset but is a legacy rate after LIBOR cessation.
- T018 receives `INVALID_CURRENCY` for `INVALID_CCY`.
- T019 receives `INVALID_CURRENCY` because `CNH` is not in the DSB ISO currency codeset used here.
- T026-T028 receive `NO_PRODUCT_DEFINITION` because `EventContract` is absent from the ANNA-DSB OTC UPI taxonomy.

The engine extracts required field names from each matched DSB template and compares the mapped fields that exist in the homework record. This is not a full production ANNA-DSB submission validator: the source portfolio does not contain a complete DSB request payload, and the solution deliberately avoids pretending that a sparse homework record can satisfy every nested schema property. Instead, the engine separates three levels of Module 2 evidence: template coverage, codeset validation, and required-attribute coverage.

Representative template-level coverage results are:

{chr(10).join(attribute_items)}

The distinction matters. `NO_PRODUCT_DEFINITION` is not the same as a parser crash. It is evidence that prediction market event contracts sit outside the current OTC product-definition library. For conventional products, missing mapped attributes are reported as schema-coverage gaps rather than legal non-compliance, because a production system would first construct a full DSB request object and then run complete JSON-schema and enum validation.

## 5. Compliance, Scope, and Conclusions

The previous single `overall_status` field is retained for compatibility, but the report now separates three dimensions:

{md_table(["Data quality status", "Count"], data_quality_rows)}

{md_table(["Reporting scope status", "Count"], scope_rows)}

{md_table(["Regulatory conclusion", "Count"], conclusion_rows)}

The compatibility status remains:

{md_table(["Overall status", "Count"], overall_rows)}

The most frequent compliance findings are shown below as "Compliance Finding Frequency by Validation Rule." Scope assessments are separated from data-quality errors so jurisdictional scope does not look like a compliance failure.

{md_table(["Compliance rule", "Count"], rule_rows)}

Scope assessments are tracked separately:

{md_table(["Scope rule", "Count"], scope_rule_rows)}

### Key Trade-Level Findings

{md_table(["Trade", "Data quality / scope", "Main findings", "Interpretation"], trade_finding_rows)}

The split is most visible in T027. A single `NOT_REPORTABLE` status would hide the fact that the record has serious visibility gaps: no LEI, no UTI, non-ISO USDC settlement, and an offshore/decentralized venue. The new fields express this more accurately: `data_quality_status = NONCOMPLIANT`, `reporting_scope_status = OUT_OF_SCOPE`, and `regulatory_conclusion = NOT_REPORTABLE_EVENT_CONTRACT`.

The EMIR margin rule is also important in the primary CFTC/EMIR validation run. T017 has `null` for collateral portfolio and margin fields. Under the assignment brief, a zero margin value must be reported as `0`; `null` is a compliance failure. The engine therefore surfaces T017 as `NONCOMPLIANT` even though some other trades legitimately report margin values of zero. The retained MAS alternative run applies the same null-versus-zero distinction for Singapore-focused analysis.

The EMIR event-contract scope treatment is intentionally transparent. T026-T028 are not forced into ordinary OTC product templates, and they are not hidden as parser failures. Instead, the engine records event-contract scope assessments and preserves the classification frontier analysis. MAS can still be run as an alternative second regime when the Singapore nexus fields are the focus.

The UTI rules also matter. T023 has a bad UTI namespace and suffix. The first 20 characters of a UTI must match the reporting counterparty LEI, and the suffix should contain only uppercase letters, digits, and hyphens.

`UPI_TEMPLATE_MAPPING` findings are kept as template-normalisation or coverage caveats rather than substantive legal failures; they are separated from the main frequency chart and excluded from the per-trade compliance bullet summary above.

## 6. Prediction Market Classification Frontier

The final three trades are the most important part of the written analysis. They are not ordinary bad records; they test whether an economically meaningful hedge still fits the existing OTC reporting perimeter.

**Key takeaway:** T026 and T028 are conditional EventContracts because they trade on a CFTC DCM but lack OTC UPI taxonomy coverage. T027 is economically hedge-like but not reportable through the CFTC/EMIR OTC path because venue, LEI, UTI, settlement-currency, and product-taxonomy infrastructure are missing.

{md_table(["Trade", "Platform", "Function", "Reporting issue", "Engine conclusion"], event_rows)}

Note: `Ambiguous` in this table corresponds to `CONDITIONAL_EVENT_CONTRACT` in `compliance_report.json`. The label reflects regulatory uncertainty pending CFTC rulemaking rather than a parser failure.

The event-contract case-file fields are treated as source facts supplied by the homework scenario. The engine separately evaluates taxonomy coverage, identifier availability, settlement-currency visibility, platform type, and reporting scope. That matters because an answer-like source label should not become the engine's only reasoning path.

T026 and T028 are Kalshi-style event contracts on a CFTC DCM. They are not conventional OTC swaps, but they are also not merely malformed trade records. The engine classifies them as `CONDITIONAL_EVENT_CONTRACT` and marks reporting scope as `CONDITIONAL`. The reason is that they can perform an economic hedging function while still falling outside standard OTC UPI reporting taxonomy.

T027 is different. It is a Polymarket/offshore/decentralized event contract with no LEIs and USDC settlement. The engine records missing LEI, missing UTI, and non-ISO settlement-currency findings, but the final conclusion is `NOT_REPORTABLE_EVENT_CONTRACT`, not ordinary OTC `NONCOMPLIANT`. This distinction is important: the trade may create economic exposure, but based on the supplied facts it is not visible through the CFTC/EMIR OTC reporting path.

The economic function test is necessary but not sufficient. A contract can transfer real economic risk and still fall outside the reporting infrastructure because of platform type, jurisdiction, legal classification, and settlement rail.

The regulatory arbitrage does not arise because the payoff is economically meaningless. It arises because economically similar risk-transfer contracts can move across venue, settlement rail, and legal classification. A licensed CFTC DCM event contract, an offshore crypto-settled market, and a bilateral OTC derivative may hedge similar exposures, but only some of them generate UPI, UTI, LEI, and trade-repository visibility. T026 and T028 are conditional because the venue is a CFTC-regulated DCM, yet the product is an event contract rather than a conventional OTC swap. T027 sits further outside the reporting perimeter because it combines offshore/decentralized venue facts, no counterparty LEIs, USDC settlement, and no CFTC DCM status.

For the EU renewable-energy firm in T026, the realistic hedge analysis would start with the economic exposure: an election result could affect subsidies, permitting, grid policy, or power-market revenues. The firm could hedge through conventional instruments such as power forwards, carbon allowances, FX/rates hedges, or structured derivatives with a regulated dealer if the exposure can be translated into market variables. A Kalshi-style event contract may be more directly linked to the political trigger, but the firm would need to check venue access, EU gambling or public-policy restrictions, board-approved hedge documentation, counterparty onboarding, and whether the hedge creates reportable derivative activity. That is exactly the frontier the engine is designed to expose: the economic hedge may be real, while the reporting classification may remain incomplete.

The supervisory blind spot is aggregation. If economically meaningful event exposures do not produce UPI, UTI, LEI, or repository records, regulators cannot easily see concentration by event, counterparty, sector, settlement currency, or jurisdiction. Stablecoin settlement worsens the visibility problem because cash movement and collateralization may sit outside standard fiat payment and margin-reporting channels. The result is not only a missing field problem; it is a market-structure problem.

The three-question economic function test provides a structured basis for distinguishing genuine hedging instruments from speculative contracts or products that fall outside the OTC reporting perimeter. A `YES` answer to all three questions is necessary but not sufficient for OTC reporting obligations; platform type, legal entity identifier coverage, and taxonomy availability must also be satisfied.

{md_table(["Trade", "Q1 Exposure", "Q2 Hedge substitute", "Q3 Price signal", "Conclusion"], economic_function_rows)}

{chr(10).join(economic_function_details)}

The key insight from this analysis is that T027 satisfies the economic-function criteria yet is classified `NOT_REPORTABLE_EVENT_CONTRACT` because the regulatory infrastructure requirements - LEI, UTI, ISO currency, regulated venue, and product taxonomy - are absent. Economic hedging intent does not create reporting infrastructure.

## 7. Proposed EventContract UPI Schema

If event contracts were brought into the reporting taxonomy, the schema should not simply copy rates, FX, or equity templates. The defining attributes should be event-specific rather than copied from conventional asset-class templates.

The ANNA-DSB OTC UPI taxonomy currently covers five conventional asset classes: Rates, Credit, FX, Equity, and Commodities. EventContracts are absent. The table below summarizes the proposed schema attributes used in the full JSON template.

{md_table(["Attribute", "Purpose"], schema_summary_rows)}

The full proposed JSON template is included in Appendix C so the main analysis remains readable while preserving the complete schema.

This schema makes three design decisions that differ from existing OTC templates. First, `PlatformType` distinguishes CFTC-regulated DCM contracts (T026, T028) from offshore and decentralised contracts (T027), enabling jurisdiction-aware scope assessment. Second, `RegulatoryStatus` records gambling or public-policy restrictions that may apply in EU jurisdictions. Third, `SettlementCurrency` explicitly accommodates stablecoin settlement while flagging non-ISO codes as a supplemental identification requirement.

Such a schema would help distinguish a licensed exchange-traded political event contract from an offshore crypto-settled contract, even if both have similar economic payoff structures.

## 8. Regulatory Arbitrage Analysis—Two Elements from Brandes (2026)

Brandes (2026) frames the classification problem around functional features: operator neutrality, real financial exposure, and incremental price discovery. For a RegTech implementation, the two most operationally relevant issues are operator neutrality and market-integrity supervision.

### 8.1 Operator Neutrality

Operator neutrality means the event-contract platform should not have financial incentives linked to a specific outcome or use its own market position to influence settlement incentives. The cross-border problem is that an EU firm accessing a CFTC DCM or an offshore platform may face venue and operator risks that are not visible through EMIR or MiFID II infrastructure. A compliance engine can only test this if platform/operator LEIs and parent-child relationships are available. For T027, no operator/counterparty LEI is available at all; for T026 and T028, the CFTC DCM status makes oversight plausible but does not by itself create ordinary OTC trade-repository visibility.

### 8.2 Market Integrity Supervision

Market-integrity supervision concerns position limits, large-trader reporting, concentration surveillance, and timing checks around political or regulatory announcements. Event contracts can be economically meaningful even when they are not standard OTC derivatives. Without a product identifier, counterparty LEIs, and repository records, regulators cannot aggregate exposures by event or detect a large position correlated with related rates, FX, commodity, or credit risk.

The engine now exposes supervisory action flags for the three event-contract trades:

{md_table(["Trade", "No UPI", "Non-ISO ccy", "ID gaps", "EC-1 threshold", "Action flag"], supervisory_flag_rows)}

Two technical CFTC modifications follow from this analysis:

{chr(10).join(cftc_recommendation_items)}

The second recommendation is deliberately phrased as a review flag for T027. The proposed USD 100,000 threshold is higher than T027's USD 50,000 notional, so an automatic filing-obligation statement would overclaim the result. The professional treatment is to mark T027 as a visibility-risk review case unless the rule threshold is lowered or the trade size increases.

## 9. Dashboard and Deliverables

The dashboard supports the report rather than replacing it, with four views: compliance heatmap, finding frequency by validation rule, asset-class breakdown, and T026-T028 classification frontier panel.

## 10. Engine Limits and CFTC Recommendations

The engine can validate structured fields, match taxonomy files, detect missing identifiers, separate zero from null, and flag business-consistency defects. It cannot determine true hedging intent, gambling classification, exchange authorization, or cross-border enforcement consequences. Those issues require legal and supervisory judgment.

This is exactly why prediction market contracts are useful in the assignment. They show the difference between field-level compliance, jurisdictional scope, and product-level classification. The engine can prove that T026-T028 do not fit the existing ANNA-DSB OTC product taxonomy, but whether and how they should be reported is a regulatory design question.

## 11. Conclusion

This project builds and tests a rule-based RegTech engine on 28 OTC-derivative and event-contract records. For conventional OTC products, the engine is able to map products through the existing UPI structure, validate UTI and LEI identifiers, and flag common reporting problems such as invalid currencies, null margin fields, timestamp defects, and missing product definitions.

The main lesson from the implementation is that not all failures mean the same thing. Some records have ordinary data-quality problems, such as bad LEIs or incomplete timestamps. Others raise scope or classification problems that cannot be solved by a stricter parser. For this reason, the final output separates data quality, reporting scope, and regulatory conclusion instead of relying only on one overall compliance label.

The event-contract cases show this distinction most clearly. T026 and T028 are treated as conditional EventContracts because they are linked to regulated prediction-market venues but do not fit the current ANNA-DSB OTC product taxonomy. T027 is the strongest visibility-gap case: it has missing LEIs, no UTI, USDC settlement, and no ordinary CFTC / EMIR reporting path, even though it may still perform an economically hedge-like function.

Overall, the project shows that existing reporting infrastructure works reasonably well for known OTC product classes, but it is less effective when economic risk transfer moves into event-based or prediction-market instruments. The proposed EventContract schema, dashboard, and CFTC-style technical recommendations are intended to show how such exposures could be made more visible without treating every jurisdictional gap as a simple data error.

## Appendix A: Team Contribution Statement

{md_table(["Student ID", "Name", "Responsibility", "Main Deliverables", "Related Module"], contribution_rows)}

All members participated in final integration, validation, and consistency review across the code outputs, written report, and dashboard. The final project was validated using the primary CFTC/EMIR run, with CFTC/MAS retained as an alternative Singapore-focused validation run.

## Appendix B: Additional Test Trades

{md_table(["Trade ID", "Scenario", "Expected result"], additional_test_rows)}

AT004 and AT005 are deliberately constructed to test LEI check-digit validation and null-margin detection respectively. AT001-AT003 are retained as clean or scope-control cases so the test plan covers both positive and negative paths.

## Appendix C: Proposed EventContract JSON Schema

The full proposed EventContract JSON schema used in Section 7 is reproduced below.

```json
{schema_json}
```
"""

    out = ROOT / "reports" / "written_report.md"
    out.write_text(content, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()

# MH6822 HW2 OTC Derivatives Trade Reporting Compliance Engine

This project implements the Homework 2 pipeline:

- Module 1: robust trade parser with declared-vs-engine parse status
- Module 2: ANNA-DSB UPI template lookup and codeset validation
- Module 3: CFTC + EMIR compliance checker, with MAS retained as an alternate regime path
- Module 4: prediction market classification analysis, economic-function tests, and EventContract schema proposal
- Bonus: standalone HTML dashboard

## Team Contribution Statement

| Matriculation Number | Name | Responsibility | Main Deliverables | Related Module |
| --- | --- | --- | --- | --- |
| G2505246J | LIU YISHAN | YISHAN002@e.ntu.edu.sg | Data pipeline and trade parser | Raw/processed data review; parser handling; nulls, bad dates, partial timestamps. | M1 / Integration |
| G2505431H | GONG PENGXIANG | GONG0093@e.ntu.edu.sg | UPI lookup and ANNA-DSB taxonomy validation | ANNA-DSB template lookup; product alias mapping; currency/reference-rate codesets; EventContract no-product-definition. | M2 / UPI Lookup Engine |
| G2506255B | GUO YIHAN | GUOY0065@e.ntu.edu.sg | Compliance checker and regime validation | LEI/UTI checks; CFTC/EMIR field validation; null-versus-zero margin logic; tests. | M3 / Testing |
| G2505266E | ZHANG JUNYI | JUNYI006@e.ntu.edu.sg | Classification analysis, report, and dashboard integration | Prediction-market analysis; economic function test; EventContract schema; regulatory arbitrage; report/dashboard integration. | M4 / Dashboard / Final Report |

> **Note:** All members participated in final integration, validation, and consistency review across the code outputs, written report, and dashboard. The final project was validated using the primary CFTC/EMIR run, with CFTC/MAS retained as an alternative Singapore-focused validation run.

## Recorded Presentation Link
https://drive.google.com/file/d/1qb7_YGOBcr9sAc-ox1x1D96l4OTNlDoe/view?usp=sharing

## Quick Start

```bash
cd HW2_solution
python -m pip install -r requirements.txt
python tools/prepare_data.py
python tools/data_audit.py
python tests_smoke.py
python run_compliance_check.py --input data/processed/trades.json --regimes CFTC,EMIR
```

`tools/prepare_data.py` makes the project self-contained:

- preserves the immutable case-file input in `data/raw/trades.json`
- writes normalized runtime data to `data/processed/trades.json`
- copies or links ANNA-DSB Product-Definitions into `data/product_definitions`
- writes `data/data_manifest.json` with raw and processed SHA-256 hashes

If no local ANNA-DSB copy exists, use:

```bash
python tools/prepare_data.py --download
```

That command clones `https://github.com/ANNA-DSB/Product-Definitions.git`, so it needs internet access.

`data/raw/trades.json` preserves the original case-file input, while `data/processed/trades.json` is the reproducible runtime copy used by the pipeline. No substantive trade economics are altered; the processed layer is used to make the execution path explicit and auditable.

The ANNA-DSB product-definition library is bundled under `data/product_definitions/` so the submission can be reproduced without re-cloning external sources. In a production setting, the exact retrieval date or repository commit hash should be pinned for auditability.

## Project Architecture

The implementation follows the teacher's Module 1-4 starter-notebook architecture while keeping one stable shared implementation layer. `src/engine.py` contains the core orchestration, parsing, UPI lookup, compliance, classification, summary, and output-writing logic used by the command-line scripts.

The visible homework module boundaries are exposed through lightweight wrappers:

- `src/module1_parser.py`: parser and business validation entry points
- `src/module2_upi.py`: ANNA-DSB UPI lookup and codeset validation entry points
- `src/module3_compliance.py`: LEI, UTI, required-field, margin, and regime checks
- `src/module4_classification.py`: event-contract source facts and classification conclusions
- `src/reporting.py`: summary and output writer entry points
- `src/utils/`: LEI and codeset utility wrappers

These wrapper modules import and re-export the stable functions from `src/engine.py`; they do not duplicate or change the compliance logic or output schema.

Architecture note: `src/engine.py` is kept as the stable shared implementation and orchestration layer. The wrapper files `module1_parser.py`, `module2_upi.py`, `module3_compliance.py`, `module4_classification.py`, and `reporting.py` expose the assignment's M1-M4 module boundaries and align the codebase with the starter architecture without duplicating logic.

This submission implements CFTC, EMIR, and MAS. EMIR is included as the primary CFTC/EMIR validation run, while MAS is retained for the Singapore reporting-nexus analysis. Other regimes such as ASIC or CSA could be added through additional regime-specific rule functions without changing the overall pipeline design.

For the primary CFTC/EMIR validation run, run CFTC plus the lightweight homework-level EMIR validator:

```bash
python run_compliance_check.py --input data/processed/trades.json --regimes CFTC,EMIR
```

For the Singapore analysis path retained in this project, run:

```bash
python run_compliance_check.py --input data/processed/trades.json --regimes CFTC,MAS
```

The EMIR implementation is a homework-level required-field and margin-null validator, not a full production EMIR Refit validator. MAS is retained because the portfolio includes Singapore reporting-nexus logic. EventContract trades T026-T028 are intentionally treated as classification-frontier cases, not parser failures.

## Data Flow

```text
data/raw/trades.json
  -> tools/prepare_data.py
  -> data/processed/trades.json
  -> tools/data_audit.py
  -> run_compliance_check.py
       -> parser and business validation
       -> ANNA-DSB UPI lookup from data/product_definitions
       -> CFTC + EMIR or CFTC + MAS rule checks
       -> prediction-market classification frontier
  -> output/*.json + output/findings.csv + dashboard/dashboard.html
  -> tools/build_report.py -> reports/written_report.md
```

The engine separates raw source facts from derived regulatory conclusions. Raw fields are preserved for auditability, while parse status, UPI status, compliance findings, scope assessments, and classification conclusions are generated by the pipeline.

## Outputs

```text
output/compliance_report.json   Full structured result by trade
output/findings.csv             Flat finding table for review
output/summary.json             Portfolio-level summary
output/data_audit.json          Data-first audit used to rebuild the report
dashboard/dashboard.html        Bonus dashboard
reports/written_report.md       Written report source
reports/written_report.docx     Word version, generated with pandoc
reports/written_report.pdf      Rendered PDF version for submission/review
reports/templates/              Pandoc Word reference assets used by the report build
```

## Dashboard

`dashboard/dashboard.html` is the main integrated dashboard entry point. Open this file directly in a browser:

```text
dashboard/dashboard.html
```

Optional full-page presentation views are also generated under `dashboard/pages/*.html` for chart-by-chart review; the main dashboard remains complete without those pages.

For a local URL instead, run:

```bash
python -m http.server 8000
```

Then visit:

```text
http://localhost:8000/dashboard/dashboard.html
```

The dashboard includes Plotly charts plus fallback HTML tables. Plotly is bundled locally under `dashboard/assets/plotly.min.js`, so the dashboard opens without internet access.

## Key Design Choices

- Runtime data lives in `data/processed/trades.json`; `data/raw/trades.json` is the immutable audit source.
- `declared_parse_status` is treated as an input fact; `engine_parse_status` is generated by the parser.
- Event-contract platform and jurisdiction fields are treated as case-file source facts. The engine separately evaluates taxonomy coverage, identifier availability, reporting visibility, and classification conclusions, rather than treating these trades as ordinary parser failures.
- Each EventContract trade carries a structured economic-function test and CFTC supervisory action flag so the dashboard/report can distinguish economic hedging logic from reportability.
- `overall_status` is retained for compatibility, but the main report now separates `data_quality_status`, `reporting_scope_status`, and `regulatory_conclusion`.
- The dashboard uses "Compliance Finding Frequency by Validation Rule"; scope assessments are separated from data-quality errors so jurisdictional scope does not look like a compliance failure.
- Product-label aliases are transparent configuration in `config/product_aliases.json`.
- The engine uses only the Python standard library. LEI ISO 7064 MOD 97-10 validation is implemented directly.
- `XAU` is treated as a valid ISO 4217 currency because it appears in the DSB currency codeset.
- `GBP-LIBOR-BBA` is a warning, not a hard error, because it remains in the codeset while being a legacy LIBOR rate.
- T017 explicitly fails EMIR/MAS margin checks because null is not the same as zero.
- T026-T028 are treated as a taxonomy/classification frontier, not ordinary parser crashes. The structured output also includes a proposed EventContract UPI schema and CFTC technical recommendations.

`NOT_REPORTABLE` does not mean clean, risk-free, or irrelevant. For T027, it means the event contract falls outside the selected CFTC/EMIR OTC reporting path, while still creating a data-visibility gap through missing LEI, missing UTI, USDC settlement, and lack of UPI taxonomy coverage. The MAS alternative run keeps the Singapore-nexus view available without making it the main submission path.

Engine limits: the current engine focuses on reporting identifiers, ANNA-DSB product-definition coverage, and field-level compliance checks. A production-grade engine could add richer business-rule validation, including date-order consistency, notional and margin reasonableness, timestamp sequencing, and additional regime modules.

## Smoke Test

```bash
python tests_smoke.py
```

The smoke test checks the main homework edge cases: LIBOR warning, XAU validity, partial timestamps/dates, null margin failure, status splitting, T026-T028 event-contract treatment, and additional report-aligned cases for LEI check-digit and null-margin detection.

## Report Rebuild Workflow

```bash
python tools/data_audit.py
python tests_smoke.py
python run_compliance_check.py --input data/processed/trades.json --regimes CFTC,EMIR
python tools/build_report.py
pandoc reports/written_report.md --reference-doc=reports/templates/written_report_reference.docx -o reports/written_report.docx
python tools/format_report_docx.py reports/written_report.docx
python tools/refine_report_layout.py reports/written_report.docx
soffice --headless --convert-to pdf --outdir reports reports/written_report.docx
```

The MAS command can be run separately for the Singapore alternative view; rerun the CFTC/EMIR command before rebuilding the primary CFTC/EMIR validation report package.

`tools/format_report_docx.py` applies the final body-level Word layout pass: professional margins and fonts, shaded report tables with light borders, a slightly denser WPS-friendly page rhythm, compact code-block styling, a concise MH6822 ASS2 header, page breaks before major report sections and Appendix A, table rows marked not to split across pages, and a simple footer with page numbering.

`reports/templates/written_report_reference.docx` is still part of the canonical build and should be kept in the repository. Pandoc uses it as the Word reference document before the repo-local OOXML post-processing steps run.

`tools/refine_report_layout.py` is the final report-layout assembly step. It rebuilds the cover page and contents page from stable Word-native OOXML, applies the Appendix C layout patch, and keeps the DOCX/PDF report package aligned with the curated report styling used in the submission files.

For visual QA of the Word report, use LibreOffice/soffice plus the bundled `render_docx.py` script. Rendered check directories are QA working files and are excluded from the final submission package.

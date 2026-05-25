# Changelog

All notable changes to the OEM Accessory Pipeline (`OEMAccessories`) are documented in this file. This follows the [Keep a Changelog](https://keepachangelog.com) format.

The versions are tracked against the date of release/deployment, and the Unreleased section captures work in progress.

---

## [Unreleased]

### Added

- **Raw data folder structure:** `data/landing_zone/{oem}/` folder inside OEMAccessories for storing OEM source Excel files
  - Self-contained project structure: data and code live together
  - One folder per OEM (mitsubishi, honda, mazda, etc.)
  - Pipeline entry point auto-discovers the most recent .xlsx file for convenience
  - Raw data folder excluded from git (sensitive pricing, large binaries)
- **Report sheet in combined output:** All pipeline runs now generate a single Excel file containing:
  - `_Report` sheet (first tab) with Run Summary (metadata), Model Profile (per-model statistics), and DQ Records (all flagged issues with part numbers for quick review)
  - Model data sheets (`{model}_{lang}`) with processed accessory data
- **Model Profile trim visibility:** Records out breakdown by trim level in the Model Profile table, formatted as multi-line text in the Records Out cell (e.g., `ES (127 EN | 127 FR)` per trim). Keeps the Model Profile table as a clean one-row-per-model structure while providing detailed trim applicability at a glance.
- Helper functions in Step 5:
  - `_build_run_summary()` — generates key-value Run Summary table with aggregate stats
  - `_build_model_profile()` — generates one-row-per-model profile with records_in/out (with trim breakdown) and DQ warnings
  - `_build_trim_records_out_text()` — formats per-trim EN/FR counts as a readable multi-line string for the Records Out cell
  - `_build_dq_records()` — extracts DQ records into a review-friendly table with issue descriptions and part info

### Changed

- **Step 5 output architecture:** Refactored to separate frame preparation from file writing
  - `run()` → `prepare_frames()` — returns `Dict[str, pd.DataFrame]` without writing to disk
  - New `write_combined_output()` function — writes all accumulated frames + Report sheet to a single combined Excel file named `{oem}_{run_id}_{timestamp}.xlsx`
  - `BasePipeline.run()` now collects frames across all sheets before writing once, enabling the Report sheet which requires run-level statistics
- **Output file strategy:** From "one file per model" to "one file per run" to simplify review and keep output directory clean
- Abstract method signatures in `BasePipeline`:
  - `run_step5_output()` return type: `None` → `Dict[str, pd.DataFrame]`
  - New abstract method: `run_write_combined_output(all_frames, run_stats, dq_logger, run_id, config, pipeline_logger)`

---

## [2026-05-19] — Initial Production Build

### Added

#### Core Pipeline

- Abstract `BasePipeline` class defining the 5-step pipeline contract (`core/base_pipeline.py`)
- `config_loader.py` for validating OEM config schemas
- Five pipeline steps for all OEMs:
  - **Step 1 (Validation):** Raw structure validation, header promotion, non-null checks, profitability checks
  - **Step 2 (Header Normalization):** Column keyword matching with word-token logic, trim boundary detection
  - **Step 3 (Standardization):** Column mapping, data type enforcement, trim value normalization
  - **Step 4 (Transformation):** Trim applicability validation, melt, language split (EN/FR)
  - **Step 5 (Output):** Metadata enrichment, column mapping for rate importer, Excel export
- Dual-logger architecture:
  - `dq_logger.py` — generates stakeholder-facing JSON DQ reports
  - `pipeline_logger.py` — generates developer-facing text execution logs
- Helper modules (`core/helpers/`):
  - `column_mapper.py` — keyword-based column matching with word-token logic
  - `header_helpers.py` — column name cleaning, header row promotion
  - `trim_helpers.py` — trim column detection and validation with `__na__` sentinel support

#### Mitsubishi OEM Pipeline

- Complete Mitsubishi pipeline implementation under `oems/mitsubishi/`
- `mitsubishi_config.json` with all business rules:
  - 7 required columns with keyword matching rules
  - Trim boundary detection (Remarks ↔ Photo/Image)
  - Trim validation with 60% data threshold
  - Non-null column validation with 50% threshold (records below threshold logged as DQ warnings, above threshold skip sheet)
  - Language-split configuration (EN/FR)
  - Rate importer output format mapping
- Mitsubishi orchestrator and 5-step pipeline modules
- Entry point: `run_mitsubishi.py`

#### Documentation

- `README.md` — Project orientation, setup, running pipelines, adding new OEMs
- `DECISIONS.md` — Design decision log (8 major architectural decisions documented)
- `CHANGELOG.md` — This file

#### Data Quality & Logging

- DQ report generation with rule-based categorization:
  - `non_null_column_rule` — Records with null values in required columns (excluded from output)
  - `profitability_rule` — Records where MSRP ≤ DNP or either ≤ 0 (included but flagged)
  - `trim_applicability_rule` — Records applying to zero trim levels (excluded)
  - `trim_candidate_failed_validation` — Trim columns that didn't meet validation criteria
- Pipeline execution log with sheet-level progress tracking and error reporting
- Output folder structure: `output/dq_reports/`, `output/pipeline_logs/`, `output/ready_to_upload/`

#### Error Handling

- Two-tier error taxonomy:
  - **FATAL errors** (structural issues) — pipeline skips the sheet, logged to `pipeline_logger`
  - **DQ warnings** (data quality issues) — records logged to `dq_logger`, processing continues
- Examples:
  - Column not found → FATAL
  - Null rate ≥ 50% → FATAL
  - Null rate < 50% → DQ warning per record, continue
  - Unprofitable record → DQ warning, include in output

### Fixed

- Header promotion bug: was promoting Row 0 (model name) instead of Row 1 (headers) — now correctly uses Row 1
- Column matching false positives: substring "en" in "french" was incorrectly matching "english" — fixed with word-token matching
- Rate import column mapping: was referencing `english_description` which no longer exists after language split — now uses `"description"`

### Changed

- (No breaking changes in initial release)

### Known Limitations

- Currently supports only Mitsubishi OEM; other OEMs require config + orchestrator
- Excel files must follow strict structure: Row 0 = model name, Row 1 = headers, Row 2+ = data
- Trim column detection relies on hardcoded boundary columns ("Remarks", "Photo"/"Image") — will need to become configurable for OEMs with different structures

---

## Future Releases

### Planned

- [ ] Support for additional OEMs (Honda, Mazda, Toyota, etc.)
- [ ] Web UI for reviewing DQ reports and triggering pipeline runs
- [ ] Scheduling and automated runs on a cadence
- [ ] Database storage of historical results for trend analysis
- [ ] More granular configuration per-column trim boundaries
- [ ] Unit and integration tests for all pipeline steps

---

## How to Read This File

- **Added** — New features or files introduced
- **Fixed** — Bug fixes and corrections
- **Changed** — Behavior changes or modifications to existing features
- **Removed** — Deprecated or removed functionality
- **Known Limitations** — Constraints and future work

Each dated section represents a release or significant milestone. The `[Unreleased]` section captures work in progress.

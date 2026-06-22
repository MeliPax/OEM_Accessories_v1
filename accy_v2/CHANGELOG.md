# Changelog

All notable changes to the OEM Accessory Pipeline (`OEMAccessories`) are documented in this file. This follows the [Keep a Changelog](https://keepachangelog.com) format.

The versions are tracked against the date of release/deployment, and the Unreleased section captures work in progress.

---

## [Unreleased]

### Added

- **Model number lookup integration (Step 4.5):** New pipeline step for enriching accessory data with vehicle model numbers
  - Batch lookup strategy: one database query per unique trim (not per row), dramatically improving performance
  - Keyword extraction and combination from multiple sources:
    - Model name from metadata (extracted in Step 1 from cell A1)
    - Fuel type from sheet name (if applicable, e.g., PHEV, EV)
    - Trim names with abbreviation expansion (e.g., "gt-p" → ["gt", "premium"])
    - Multi-character hyphenated terms preserved as single keywords (e.g., "s-awc" stays as one keyword, not split)
  - Intelligent trim parsing: single-letter abbreviations expanded via library (p→premium, n→noir), multi-character terms kept intact
  - Row filtering: rows with missing/ambiguous model lookups excluded from output automatically
  - `model_number_status` column added to output for visibility ("yes - Model number found" or "no - missing model number")
  - DQ logging: missing trims flagged with details (keywords searched, lookup result type, rows affected)

- **Raw data folder structure:** `data/landing_zone/{oem}/` folder inside OEMAccessories for storing OEM source Excel files
  - Self-contained project structure: data and code live together
  - One folder per OEM (mitsubishi, honda, mazda, etc.)
  - Pipeline entry point auto-discovers the most recent .xlsx file for convenience
  - Raw data folder excluded from git (sensitive pricing, large binaries)

- **Report sheet in combined output:** All pipeline runs now generate a single Excel file containing:
  - `_Report` sheet (first tab) with Run Summary (metadata), Model Profile (per-model statistics), and DQ Records (all flagged issues with part numbers for quick review)
  - Model data sheets (`{model}_{lang}`) with processed accessory data
  - Model Profile trim visibility: Records out breakdown by trim level formatted as multi-line text

- Helper functions in Step 5:
  - `_build_run_summary()` — generates key-value Run Summary table with aggregate stats
  - `_build_model_profile()` — generates one-row-per-model profile with records_in/out (with trim breakdown) and DQ warnings
  - `_build_trim_records_out_text()` — formats per-trim EN/FR counts as readable multi-line string
  - `_build_dq_records()` — extracts DQ records into review-friendly table

### Changed

- **Output paths structure:** Changed from `output/` to `accy_v2/output/` in OEM configs for consistency with project structure
- **Keyword extraction logic:** Model keywords now extracted from meta_data["model_name"] (populated by Step 1) instead of only from sheet name, ensuring complete keyword context even when sheet names are abbreviated
- **Trim abbreviation parsing:** Single-letter abbreviations (p, n, s) still expand via library, but multi-character hyphenated terms (s-awc, fwd) now stay as single keywords to match database descriptions
- **CSV path resolution:** Fixed database CSV path computation to use absolute paths from script location, solving portability issues when run from different directories
- **Step 5 output architecture:** Refactored to separate frame preparation from file writing
  - `run()` → `prepare_frames()` — returns `Dict[str, pd.DataFrame]` without writing to disk
  - New `write_combined_output()` function — writes all accumulated frames + Report sheet to single combined Excel file
  - `BasePipeline.run()` now collects frames before writing once
- Abstract method signatures in `BasePipeline`:
  - `run_step5_output()` return type: `None` → `Dict[str, pd.DataFrame]`
  - New abstract method: `run_write_combined_output(all_frames, run_stats, dq_logger, run_id, config, pipeline_logger)`
  - New abstract method: `run_step4_5_model_enrichment()` for vehicle model lookup

### Fixed

- **Database path resolution:** CSV file not found when running from different working directories — now uses absolute path computed from script location (Path(__file__).parent.parent.parent.parent.parent)
- **Keyword extraction from sheet names:** Sheet names like "2026 PHEV" (without model name) now correctly extract fuel type while pulling model name from metadata, preventing lookup failures
- **Trim keyword splitting:** Multi-character hyphenated terms like "s-awc" no longer incorrectly split into separate keywords, matching actual database description format

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

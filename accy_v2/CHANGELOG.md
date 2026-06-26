# Changelog

All notable changes to the OEM Accessory Pipeline (`OEMAccessories`) are documented in this file. This follows the [Keep a Changelog](https://keepachangelog.com) format.

The versions are tracked against the date of release/deployment, and the Unreleased section captures work in progress.

---

## [Unreleased]

### Added

- **Trim exclusion keywords filter (June 26, 2026):** Configurable exclusion list for structural category-header columns
  - New config key: `trim_exclusion_keywords` in OEM config files
  - Filters candidate trim columns BEFORE validation, preventing spurious DQ warnings
  - Substring + case-insensitive matching (e.g., "category" matches "CATEGORY", "CARGO" matches "CARGO_ITEMS")
  - Applied to Mitsubishi: ["category", "electronics", "interior", "exterior", "cargo", "general"]
  - Reduces `trim_candidate_failed_validation` DQ noise while maintaining clean trim detection
  - Default-safe: empty list = no filtering; OEMs without key unaffected

- **Model number lookup integration (Step 4.5):** New pipeline step for enriching accessory data with vehicle model numbers
  - Batch lookup strategy: one database query per unique trim (not per row), dramatically improving performance
  - Keyword extraction and combination from multiple sources:
    - Model name from metadata (extracted in Step 1 from cell A1)
    - Fuel type from sheet name (if applicable, e.g., PHEV, EV)
    - Trim names with abbreviation expansion (e.g., "gt-p" → ["gt", "premium"])
    - Multi-character hyphenated terms preserved as single keywords (e.g., "s-awc" stays as one keyword, not split)
  - Intelligent trim parsing: single-letter abbreviations expanded via library (p→premium, n→noir), multi-character terms kept intact
  - Row filtering: rows with missing/ambiguous model lookups excluded from output automatically
  - DQ logging: missing trims flagged with details (keywords searched, lookup result type, rows affected)

- **Per-manufacturer vocabulary filtering (June 23, 2026):** Solved model lookup false positives
  - Vocabulary JSON files generated for each manufacturer containing all unique tokens from Description column
  - Trim discriminator categorization: separates trim-level identifiers (premium, noir, se, es, gt) from specifications (fwd, awc, s-awc, manual, cvt)
  - Post-filter in search: excludes results with extra trim discriminators but allows specification variations
  - Auto-regenerating vocabularies: vocabularies rebuild whenever CSV database is updated
  - Exact matching behavior: `["outlander", "phev", "gt"]` returns only GT variant, not GT-Premium

- **model_lookup module relocated (June 23, 2026):** Moved from project root into accy_v2
  - Better project organization: colocate vehicle model database with pipeline code
  - All paths automatically resolve using Path(__file__).parent relative navigation
  - Dual-import support: works both from accy_v2 and model_lookup/ directories
  - Package structure: added __init__.py files for proper Python package support

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
  - `_build_run_summary()` — generates key-value Run Summary table with aggregate stats and manager analytics
  - `_build_model_profile()` — generates one-row-per-model profile with records_in/out (with trim breakdown) and DQ warnings
  - `_build_trim_records_out_text()` — formats per-trim EN/FR counts as readable multi-line string
  - `_build_dq_records()` — extracts DQ records into review-friendly table

- **Manager analytics in Run Summary (June 24, 2026):** Enhanced dashboard with strategic health indicators
  - Sheets/Models Processed: consolidated metric showing processing scope
  - Source Accessories / Output Records: distinct units clearly labeled
  - Trim Coverage: percentage of model-trim lookups that succeeded
  - DQ Warnings by Rule: breakdown showing which issue types dominate
  - Model Lookup Issues: categorized by failure type (No Match, No Keywords, Lookup Error) with percentages
  - Sheet health metrics: sheets with issues and clean sheets as % of total

### Changed

- **Output columns (June 23, 2026):** Removed `model_number_status` from final export
  - Output now contains: Part Description, Comments, Price, Hours, Trim, model_number (cleaner parts list)
  - Status still generated internally for DQ reporting, but filtered out before Excel export

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

- **Data boundary detection: use ALL required fields, not just part_number (June 26, 2026):** Incomplete tail rows now properly removed
  - Root cause: `_trim_to_data_range()` only checked part_number presence, allowing rows with part# but missing description/msrp/install_time
  - Solution: Expanded legit_mask to check ALL `non_null_columns` from config (part_number, english_description, msrp, install_time)
  - Impact: Tail rows with partial data now removed in Step 1 (data cleaning), not left for DQ warnings later
  - Example: 2024 Mirage — 40 non_null_column DQ violations → 0 (all incomplete rows trimmed)
  - Boundary detection now correctly identifies last row with ALL required fields, not just any part number

- **Execution order: drop brochures before trimming data range (June 26, 2026):** Last-row detection now lands on real accessories, not brochures
  - Root cause: Brochure records (YYYY*BROE/BROF) have part numbers, so `_trim_to_data_range()` treated them as real data when finding last_idx
  - Solution: Swapped execution order in step1 — `_drop_brochure_records()` now runs BEFORE `_trim_to_data_range()`
  - Benefit: After brochures removed, last_idx correctly identifies last real accessory; any brochures or notes after it become proper "tail"
  - Example: 2026 Eclipse Cross — boundary moved [0–123] → [0–121]; 2024 Mirage [0–127] → [0–114] + 11 tail rows detected

- **Run Summary "Records Excluded" metric (June 24, 2026):** Replaced incompatible unit comparison with honest metrics
  - Root cause: `records_in` (wide-format, one row per accessory) vs `records_out` (long-format, EN+FR×trim combinations) are incompatible units — always produced negative values (-876%)
  - Solution: Added `Source Accessories` and `Output Records` with explicit unit labels, plus `Trim Coverage` (successful trim lookups / total trims attempted) at the grain where exclusions actually happen
  - Result: Managers now see sensible metrics (e.g., "57 of 62 unique model-trim combos matched (91.9%)")
- **DQ Warnings by Rule breakdown:** Now includes percentage breakdown per rule type (e.g., "non_null_column_rule: 82 (61%) | profitability_rule: 44 (33%)")
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
